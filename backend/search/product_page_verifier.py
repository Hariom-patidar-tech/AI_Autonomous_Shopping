from __future__ import annotations

import datetime
import json
import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.schemas.product import Product, ProductOffer
from backend.search.base import RawSearchResult
from backend.search.extractor import ProductPageExtractor
from backend.search.verifier import ImageVerifier, URLVerifier

logger = logging.getLogger("shopping_agent.search.product_page_verifier")


class ProductPageVerifier:
    """Accept only current offer data embedded in a retailer's exact product page."""

    @classmethod
    async def verify(cls, raw: RawSearchResult, client: httpx.AsyncClient) -> Optional[Product]:
        valid, url_status, product_url = URLVerifier.verify_url(raw.url)
        if not valid or not URLVerifier.is_product_page_url(product_url):
            return None

        try:
            response = await client.get(product_url, timeout=10.0)
            if response.status_code != 200 or "text/html" not in response.headers.get("content-type", "").lower():
                return None
            final_url = str(response.url)
            final_valid, final_status, verified_url = URLVerifier.verify_url(final_url)
            if not final_valid or not URLVerifier.is_product_page_url(verified_url):
                return None
            return cls.from_html(raw, response.text, verified_url, final_status or url_status)
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Retailer product page could not be verified (%s): %s", raw.url, exc)
            return None

    @classmethod
    def from_html(
        cls,
        raw: RawSearchResult,
        page_html: str,
        product_url: str,
        verification_status: str = "verified",
    ) -> Optional[Product]:
        if not URLVerifier.is_product_page_url(product_url):
            return None

        soup = BeautifulSoup(page_html, "html.parser")
        product_data = cls._find_product_schema(soup)
        page_title = cls._meta_content(soup, "og:title", "twitter:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        product_name = cls._text(product_data.get("name")) or page_title or raw.title
        if not product_name or cls._is_generic_title(product_name):
            return None

        image_value = product_data.get("image") or cls._meta_content(soup, "og:image", "twitter:image")
        image_url = cls._first_image(image_value, product_url)
        image_url = ImageVerifier.verify_image(image_url)
        if not image_url:
            return None

        structured_offers = product_data.get("offers")
        if isinstance(structured_offers, dict):
            structured_offers = [structured_offers]
        if not isinstance(structured_offers, list):
            structured_offers = []

        verified_offers: list[ProductOffer] = []
        retailer = cls._retailer_name(product_url, raw.source)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for offer_data in structured_offers:
            if not isinstance(offer_data, dict):
                continue
            price = cls._offer_price(offer_data)
            currency = str(offer_data.get("priceCurrency") or "").upper()
            if price is None or not re.fullmatch(r"[A-Z]{3}", currency):
                continue
            availability = cls._availability(offer_data.get("availability"))
            seller_data = offer_data.get("seller")
            seller = cls._text(seller_data.get("name")) if isinstance(seller_data, dict) else cls._text(seller_data)
            verified_offers.append(
                ProductOffer(
                    platform=retailer,
                    seller=seller or retailer,
                    price=price,
                    currency=currency,
                    availability=availability,
                    url=product_url,
                    image_url=image_url,
                    observed_at=now,
                    verification_status=verification_status,
                )
            )

        if not verified_offers:
            meta_price = cls._meta_content(soup, "product:price:amount", "og:price:amount", "itemprop:price")
            meta_currency = cls._meta_content(soup, "product:price:currency", "og:price:currency", "itemprop:pricecurrency")
            price = cls._parse_price(meta_price)
            currency = (meta_currency or "").upper()
            if price is None or not re.fullmatch(r"[A-Z]{3}", currency):
                return None
            availability = cls._availability(cls._meta_content(soup, "product:availability", "og:availability", "itemprop:availability"))
            verified_offers.append(
                ProductOffer(
                    platform=retailer,
                    seller=retailer,
                    price=price,
                    currency=currency,
                    availability=availability,
                    url=product_url,
                    image_url=image_url,
                    observed_at=now,
                    verification_status=verification_status,
                )
            )

        brand_value = product_data.get("brand")
        brand = cls._text(brand_value.get("name")) if isinstance(brand_value, dict) else cls._text(brand_value)
        model = cls._text(product_data.get("model") or product_data.get("mpn") or product_data.get("sku"))
        inferred_brand, inferred_model = ProductPageExtractor._extract_brand_model(product_name)
        brand = brand or inferred_brand
        model = model or inferred_model
        primary_offer = verified_offers[0]
        availability = primary_offer.availability
        return Product(
            product_name=product_name,
            brand=brand,
            model=model,
            price=primary_offer.price,
            currency=primary_offer.currency,
            seller=primary_offer.seller,
            availability=availability,
            url=product_url,
            image_url=image_url,
            source=retailer,
            source_url=product_url,
            relevance_score=1.0,
            is_exact_match=True,
            verification_status=verification_status,
            observed_at=now,
            last_verified_at=now,
            offers=verified_offers,
        )

    @classmethod
    def _find_product_schema(cls, soup: BeautifulSoup) -> dict[str, Any]:
        def visit(value: Any) -> Optional[dict[str, Any]]:
            if isinstance(value, list):
                for item in value:
                    found = visit(item)
                    if found:
                        return found
            elif isinstance(value, dict):
                item_types = value.get("@type", [])
                if isinstance(item_types, str):
                    item_types = [item_types]
                if any(str(item_type).lower().endswith("product") for item_type in item_types):
                    return value
                return visit(value.get("@graph"))
            return None

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            product = visit(data)
            if product:
                return product
        return {}

    @staticmethod
    def _meta_content(soup: BeautifulSoup, *names: str) -> Optional[str]:
        for name in names:
            key, _, value = name.partition(":")
            attr_name = "itemprop" if key == "itemprop" else "property"
            attr_value = value if key == "itemprop" else name
            tag = soup.find("meta", attrs={attr_name: re.compile(rf"^{re.escape(attr_value)}$", re.I)})
            if tag and tag.get("content"):
                return str(tag["content"]).strip()
        return None

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        if isinstance(value, str):
            clean = re.sub(r"\s+", " ", value).strip()
            return clean or None
        return None

    @staticmethod
    def _first_image(value: Any, base_url: str) -> Optional[str]:
        if isinstance(value, list):
            for candidate in value:
                image = ProductPageVerifier._first_image(candidate, base_url)
                if image:
                    return image
            return None
        if isinstance(value, dict):
            value = value.get("url") or value.get("contentUrl")
        if isinstance(value, str):
            return urljoin(base_url, value.strip())
        return None

    @staticmethod
    def _offer_price(offer: dict[str, Any]) -> Optional[float]:
        price = offer.get("price")
        if price is None and isinstance(offer.get("priceSpecification"), dict):
            price = offer["priceSpecification"].get("price")
        return ProductPageVerifier._parse_price(price)

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        try:
            price = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None
        return price if 0 < price <= 100_000_000 else None

    @staticmethod
    def _availability(value: Any) -> Optional[bool]:
        text = str(value or "").lower()
        if any(state in text for state in ("instock", "limitedavailability", "preorder", "presale")):
            return True
        if any(state in text for state in ("outofstock", "soldout", "discontinued")):
            return False
        return None

    @staticmethod
    def _retailer_name(page_url: str, fallback: str) -> str:
        host = (urlparse(page_url).hostname or "").lower().removeprefix("www.")
        names = {
            "amazon": "Amazon", "flipkart": "Flipkart", "croma": "Croma",
            "reliancedigital": "Reliance Digital", "walmart": "Walmart",
            "bestbuy": "Best Buy", "ebay": "eBay", "boat-lifestyle": "boAt",
            "gonoise": "Noise", "nykaa": "Nykaa", "myntra": "Myntra",
            "ajio": "AJIO", "tatacliq": "Tata CLiQ",
        }
        for domain_part, name in names.items():
            if domain_part in host:
                return name
        return fallback or host

    @staticmethod
    def _is_generic_title(title: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        generic_titles = {
            "home", "home page", "search", "search results", "products", "all products",
            "earbuds", "wireless earbuds", "earbuds wired or wireless", "amazon in earbuds",
        }
        return normalized in generic_titles