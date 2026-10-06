from __future__ import annotations
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
from typing import List, Optional, Any
import httpx

from providers.base import BaseProvider, NormalizedProduct

logger = logging.getLogger("shopping_agent.providers.amazon")


class AmazonProvider(BaseProvider):
    """
    Official Amazon Product Advertising API (PA-API v5) and Creator API connector.
    Zero mock, dummy, or hardcoded products.
    Uses official AWS SigV4 / Creator API authentication.
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        partner_tag: Optional[str] = None,
        host: Optional[str] = None,
        region: Optional[str] = None,
        creator_token: Optional[str] = None,
    ):
        self.access_key = access_key or os.getenv("AMAZON_ACCESS_KEY", "").strip()
        self.secret_key = secret_key or os.getenv("AMAZON_SECRET_KEY", "").strip()
        self.partner_tag = partner_tag or os.getenv("AMAZON_ASSOCIATE_TAG", os.getenv("AMAZON_PARTNER_TAG", "")).strip()
        self.host = host or os.getenv("AMAZON_HOST", "webservices.amazon.in").strip()
        self.region = region or os.getenv("AMAZON_REGION", "eu-west-1").strip()
        self.creator_token = creator_token or os.getenv("AMAZON_CREATOR_TOKEN", "").strip()
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "Amazon"

    async def is_available(self) -> bool:
        """Available only if official API credentials are configured in environment."""
        if self.creator_token:
            return True
        return bool(self.access_key and self.secret_key and self.partner_tag)

    def get_status_message(self) -> str:
        if self.last_error:
            return f"Amazon API error: {self.last_error}"
        if not self.access_key or not self.secret_key or not self.partner_tag:
            return "Amazon API unavailable (AMAZON_ACCESS_KEY / AMAZON_ASSOCIATE_TAG not configured in .env)"
        return "Amazon API ready"

    def _sign_aws4(self, payload_bytes: bytes, date_stamp: str, amz_date: str) -> dict:
        """Generate AWS SigV4 headers for Amazon PA-API v5."""
        service = "ProductAdvertisingAPI"
        canonical_uri = "/paapi5/searchitems"
        canonical_querystring = ""
        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        canonical_request = (
            f"POST\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n"
            f"{signed_headers}\n{payload_hash}"
        )

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{service}/aws4_request"
        string_to_sign = (
            f"{algorithm}\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(("AWS4" + self.secret_key).encode("utf-8"), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-amz-date": amz_date,
            "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
            "Authorization": authorization_header,
        }

    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Query Amazon official API and return verified normalized products."""
        if not await self.is_available():
            logger.info("Amazon official API skipped: missing credentials.")
            return []

        # If Creator API Token is configured, query Creators API
        if self.creator_token:
            return await self._search_creator_api(query, limit)

        # PA-API v5 SearchItems
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            amz_date = now.strftime("%Y%m%dT%H%M%SZ")
            date_stamp = now.strftime("%Y%m%d")

            payload = {
                "Keywords": query,
                "SearchIndex": "All",
                "ItemCount": min(max(1, limit), 10),
                "PartnerTag": self.partner_tag,
                "PartnerType": "Associates",
                "Resources": [
                    "ItemInfo.Title",
                    "ItemInfo.ByLineInfo",
                    "ItemInfo.Classifications",
                    "Images.Primary.Large",
                    "Offers.Listings.Price",
                    "Offers.Listings.Availability.Message",
                    "Offers.Listings.Availability.Type",
                ],
            }
            payload_bytes = json.dumps(payload).encode("utf-8")
            headers = self._sign_aws4(payload_bytes, date_stamp, amz_date)

            url = f"https://{self.host}/paapi5/searchitems"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, content=payload_bytes)

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_paapi_response(data)
            else:
                err_text = resp.text[:300]
                logger.warning(f"Amazon PA-API returned HTTP {resp.status_code}: {err_text}")
                self.last_error = f"HTTP {resp.status_code}: {err_text}"
                return []

        except Exception as exc:
            logger.warning(f"Amazon PA-API request error: {exc}")
            self.last_error = str(exc)
            return []

    async def _search_creator_api(self, query: str, limit: int) -> List[NormalizedProduct]:
        """Support Amazon Creators API."""
        try:
            url = f"https://api.amazon.com/creator/products/search"
            headers = {
                "Authorization": f"Bearer {self.creator_token}",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"keyword": query, "count": limit}, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_creator_response(data)
            else:
                self.last_error = f"Creator API HTTP {resp.status_code}"
                return []
        except Exception as exc:
            self.last_error = str(exc)
            return []

    def _parse_paapi_response(self, data: dict) -> List[NormalizedProduct]:
        products: List[NormalizedProduct] = []
        search_result = data.get("SearchResult", {})
        items = search_result.get("Items", [])

        for item in items:
            try:
                asin = item.get("ASIN")
                detail_url = item.get("DetailPageURL")
                item_info = item.get("ItemInfo", {})
                title = item_info.get("Title", {}).get("DisplayValue")
                brand = item_info.get("ByLineInfo", {}).get("Brand", {}).get("DisplayValue")

                # Extract price
                offers = item.get("Offers", {}).get("Listings", [])
                if not offers:
                    continue
                price_obj = offers[0].get("Price", {})
                price_val = price_obj.get("Amount")
                currency = price_obj.get("Currency", "INR").upper()

                if not price_val or float(price_val) <= 0:
                    continue
                price = float(price_val)

                # Thumbnail
                image_url = item.get("Images", {}).get("Primary", {}).get("Large", {}).get("URL")
                if not image_url or not image_url.startswith("http"):
                    continue

                # Exact detail URL validation
                if not detail_url or not re.search(r"/(?:dp|gp/product|gp/aw/d)/[A-Za-z0-9]{6,}", detail_url):
                    continue

                availability = True
                avail_type = offers[0].get("Availability", {}).get("Type")
                if avail_type and "out" in str(avail_type).lower():
                    availability = False

                prod = NormalizedProduct(
                    product_id=asin or detail_url,
                    name=title,
                    brand=brand,
                    model=None,
                    variant=None,
                    price=price,
                    currency=currency,
                    thumbnail=image_url,
                    retailer="Amazon",
                    product_url=detail_url,
                    availability=availability,
                    verified=True,
                )
                products.append(prod)
            except Exception as e:
                logger.debug(f"Failed to parse Amazon item: {e}")
                continue

        logger.info(f"Amazon PA-API returned {len(products)} verified products.")
        return products

    def _parse_creator_response(self, data: dict) -> List[NormalizedProduct]:
        products: List[NormalizedProduct] = []
        for item in data.get("products", []):
            try:
                price = float(item.get("price", {}).get("amount", 0))
                if price <= 0:
                    continue
                products.append(
                    NormalizedProduct(
                        product_id=str(item.get("asin") or item.get("id")),
                        name=item.get("title", ""),
                        brand=item.get("brand"),
                        price=price,
                        currency=item.get("price", {}).get("currency", "INR"),
                        thumbnail=item.get("imageUrl", ""),
                        retailer="Amazon",
                        product_url=item.get("detailPageUrl", ""),
                        availability=item.get("inStock", True),
                        verified=True,
                    )
                )
            except Exception:
                continue
        return products
