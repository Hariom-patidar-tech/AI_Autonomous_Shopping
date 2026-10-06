from __future__ import annotations
import re
from typing import Tuple, Optional, Any

from backend.search.verifier import URLVerifier, ImageVerifier

GENERIC_TITLES = {
    "home", "home page", "search", "search results", "products", "all products",
    "watches", "smartwatches", "best watches", "store", "online store", "collection",
    "amazon in", "flipkart", "categories", "department",
}

BLOCKED_URL_SUBSTRINGS = [
    "/search", "/s?", "/pr?sid=", "/category", "/collections", "/stores",
    "/shop", "/browse", "/all-products", "/deals", "/offers",
]


class ProductValidator:
    """
    Strict Deterministic Product Validator.
    Never loosens validation to make products appear.
    Rejects generic pages, missing prices, unknown currency, placeholder thumbnails, broken URLs.
    """

    @classmethod
    def validate(cls, item: Any) -> Tuple[bool, Optional[str]]:
        """
        Validates NormalizedProduct or Product schema.
        Returns: (is_valid, rejection_reason)
        """
        # 1. Product Name / Title check
        name = getattr(item, "name", None) or getattr(item, "product_name", None)
        if not name or not isinstance(name, str) or len(name.strip()) < 3:
            return False, "Missing or invalid product name"

        norm_title = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        if norm_title in GENERIC_TITLES:
            return False, f"Generic title rejected: '{name}'"

        # 2. Price check
        price = getattr(item, "price", None)
        if price is None:
            return False, "Missing price"
        try:
            price_val = float(price)
            if price_val <= 0 or price_val > 100_000_000:
                return False, f"Invalid price value: {price_val}"
        except (ValueError, TypeError):
            return False, "Unparseable price"

        # 3. Currency check
        currency = getattr(item, "currency", None) or "INR"
        currency = str(currency).upper().strip()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            return False, f"Unknown currency code: '{currency}'"

        # 4. Exact product URL check
        product_url = getattr(item, "product_url", None) or getattr(item, "url", None)
        if not product_url or not isinstance(product_url, str):
            return False, "Missing product URL"

        url_str = product_url.strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://")):
            return False, f"Invalid URL scheme: {url_str}"

        # Must NOT be a generic category/search/homepage page
        lower_url = url_str.lower()
        if any(blocked in lower_url for blocked in BLOCKED_URL_SUBSTRINGS):
            return False, f"Generic search/category URL rejected: {url_str}"

        valid_url, status, _ = URLVerifier.verify_url(url_str)
        if not valid_url:
            return False, f"Untrusted or blocked URL domain: {url_str}"

        if not URLVerifier.is_product_page_url(url_str):
            return False, f"Not an exact product detail page: {url_str}"

        # 5. Thumbnail check
        thumbnail = getattr(item, "thumbnail", None) or getattr(item, "image_url", None)
        if not thumbnail or not isinstance(thumbnail, str):
            return False, "Missing product thumbnail"

        verified_thumb = ImageVerifier.verify_image(thumbnail)
        if not verified_thumb:
            return False, f"Unverified or placeholder thumbnail rejected: {thumbnail}"

        # 6. Retailer check
        retailer = getattr(item, "retailer", None) or getattr(item, "source", None)
        if not retailer or not isinstance(retailer, str) or len(retailer.strip()) < 2:
            return False, "Unknown retailer"

        # 7. Verification flag check
        verified = getattr(item, "verified", True)
        if not verified:
            return False, "Product marked unverified"

        return True, None
