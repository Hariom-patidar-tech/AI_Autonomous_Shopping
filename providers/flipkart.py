from __future__ import annotations
import logging
import os
import re
from typing import List, Optional, Any
import httpx

from providers.base import BaseProvider, NormalizedProduct

logger = logging.getLogger("shopping_agent.providers.flipkart")


class FlipkartProvider(BaseProvider):
    """
    Official Flipkart Affiliate & Product Search API connector.
    Zero mock, dummy, or hardcoded products.
    Strictly uses official Affiliate API data; does NOT scrape HTML as primary solution.
    If access is restricted/unavailable, honestly reports provider status.
    """

    def __init__(
        self,
        affiliate_id: Optional[str] = None,
        affiliate_token: Optional[str] = None,
    ):
        self.affiliate_id = affiliate_id or os.getenv("FLIPKART_AFFILIATE_ID", os.getenv("FLIPKART_TRACKING_ID", "")).strip()
        self.affiliate_token = affiliate_token or os.getenv("FLIPKART_AFFILIATE_TOKEN", "").strip()
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "Flipkart"

    async def is_available(self) -> bool:
        """Available only if official credentials are provided in environment."""
        return bool(self.affiliate_id and self.affiliate_token)

    def get_status_message(self) -> str:
        if self.last_error:
            return f"Flipkart API error: {self.last_error}"
        if not self.affiliate_id or not self.affiliate_token:
            return "Flipkart API unavailable (FLIPKART_AFFILIATE_ID / FLIPKART_AFFILIATE_TOKEN not configured in .env)"
        return "Flipkart API ready"

    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Query Flipkart official Affiliate API and return verified normalized products."""
        if not await self.is_available():
            logger.info("Flipkart official API skipped: missing credentials.")
            return []

        endpoint = f"https://affiliate-api.flipkart.net/affiliate/1.0/search.json"
        headers = {
            "Fk-Affiliate-Id": self.affiliate_id,
            "Fk-Affiliate-Token": self.affiliate_token,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; ShoppingAgent/1.0)",
        }
        params = {
            "query": query,
            "resultCount": min(max(1, limit), 10),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(endpoint, headers=headers, params=params)

            # Check if response is HTML or error page
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" in content_type or resp.text.strip().startswith("<"):
                err_msg = (
                    f"Flipkart Affiliate API returned HTML (status {resp.status_code}) instead of JSON. "
                    "Affiliate account access may be restricted or inactive."
                )
                logger.warning(err_msg)
                self.last_error = f"API returned HTML (status {resp.status_code}); access restricted"
                return []

            if resp.status_code != 200:
                logger.warning(f"Flipkart Affiliate API returned HTTP {resp.status_code}: {resp.text[:200]}")
                self.last_error = f"HTTP {resp.status_code}"
                return []

            data = resp.json()
            return self._parse_flipkart_json(data)

        except Exception as exc:
            logger.warning(f"Flipkart Affiliate API request failed: {exc}")
            self.last_error = str(exc)
            return []

    def _parse_flipkart_json(self, data: dict) -> List[NormalizedProduct]:
        products: List[NormalizedProduct] = []
        raw_items = data.get("productItemList") or data.get("products") or []

        for item in raw_items:
            try:
                base_info = item.get("productBaseInfoV1", {}) or item.get("productBaseInfo", {}) or item
                product_id = base_info.get("productId")
                title = base_info.get("title")
                brand = base_info.get("productBrand")
                product_url = base_info.get("productUrl")

                # Price extraction
                price_obj = base_info.get("flipkartSellingPrice") or base_info.get("sellingPrice") or {}
                amount = price_obj.get("amount")
                currency = price_obj.get("currency", "INR").upper()

                if not amount or float(amount) <= 0:
                    continue
                price = float(amount)

                # Thumbnail extraction
                image_urls = base_info.get("imageUrls") or {}
                thumbnail = None
                if isinstance(image_urls, dict):
                    # Pick highest resolution
                    for res in ["800x800", "400x400", "200x200", "unknown"]:
                        if image_urls.get(res):
                            thumbnail = image_urls[res]
                            break
                    if not thumbnail and image_urls:
                        thumbnail = next(iter(image_urls.values()), None)
                elif isinstance(image_urls, list) and image_urls:
                    thumbnail = image_urls[0]

                if not thumbnail or not thumbnail.startswith("http"):
                    continue

                # Exact detail URL validation
                if not product_url or not re.search(r"/p/[A-Za-z0-9]+", product_url):
                    continue

                in_stock = base_info.get("inStock", True)

                prod = NormalizedProduct(
                    product_id=str(product_id or product_url),
                    name=title,
                    brand=brand,
                    model=None,
                    variant=None,
                    price=price,
                    currency=currency,
                    thumbnail=thumbnail,
                    retailer="Flipkart",
                    product_url=product_url,
                    availability=bool(in_stock),
                    verified=True,
                )
                products.append(prod)
            except Exception as e:
                logger.debug(f"Failed to parse Flipkart item: {e}")
                continue

        logger.info(f"Flipkart API returned {len(products)} verified products.")
        return products
