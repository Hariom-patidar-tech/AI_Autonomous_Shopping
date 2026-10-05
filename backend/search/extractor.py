from __future__ import annotations
import re
import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
from backend.search.base import RawSearchResult, SearchCandidate
from backend.search.verifier import URLVerifier, ImageVerifier
from backend.schemas.product import Product, ProductOffer

logger = logging.getLogger("shopping_agent.extractor")

NON_PRODUCT_DOMAINS = {
    "wikipedia.org",
    "wiktionary.org",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "reddit.com",
    "quora.com",
    "pinterest.com",
    "newworldencyclopedia.org",
    "britannica.com",
}

NON_COMMERCIAL_TLDS = (".gov", ".gov.in", ".nic.in", ".ac.in", ".edu", ".mil")


class CandidateDetector:
    """Detects whether a raw search result is a valid product candidate."""

    @staticmethod
    def is_candidate(result: RawSearchResult) -> bool:
        domain = result.domain.lower()
        url_lower = result.url.lower()

        # Reject educational, government, military domains
        if any(domain.endswith(tld) or f"{tld}/" in domain for tld in NON_COMMERCIAL_TLDS):
            return False

        # Reject obvious non-commerce social / forum / wiki / encyclopedia domains
        if any(np in domain for np in NON_PRODUCT_DOMAINS):
            return False
        if any(bad in domain for bad in ["encyclopedia", "dictionary", "tribunal", "judiciary", "admissions", "iimcat"]):
            return False

        # Reject video and auth URLs
        if any(x in url_lower for x in ["/watch?v=", "/login", "/signup", "/cart", "/checkout"]):
            return False

        # If it has a verified price or is from a recognized retailer, it's a product candidate
        if result.price_text:
            return True

        title_lower = result.title.lower()
        snippet_lower = result.snippet.lower()
        commerce_cues = [
            "buy", "price", "sale", "online", "store", "shop", "inr", "rs.", "₹", "off", "deal",
            "t-shirt", "tshirt", "shirt", "shoe", "shoes", "laptop", "phone", "tv", "camera",
            "free delivery", "order", "purchase", "specs", "flipkart", "amazon", "croma", "myntra", "ajio"
        ]

        # Must have at least one recognized commercial or product cue
        has_cue = any(cue in title_lower or cue in snippet_lower or cue in url_lower for cue in commerce_cues)
        if not has_cue:
            return False

        return True


class ProductPageExtractor:
    """Extracts normalized Product models from search candidates without inventing data."""

    @classmethod
    def extract(cls, raw: RawSearchResult) -> Optional[Product]:
        # 1. URL Verification
        is_valid, status, verified_url = URLVerifier.verify_url(raw.url)
        if not is_valid:
            logger.debug(f"Rejected candidate due to unverified URL: {raw.url}")
            return None

        # 2. Extract clean product name
        cleaned_name = cls._clean_title(raw.title)
        if len(cleaned_name) < 3:
            return None

        # 3. Extract Price (strictly None if not found)
        combined_text = " ".join(
            part for part in [raw.price_text, raw.snippet, raw.title] if part
        )
        price, currency = cls._extract_price_and_currency(combined_text)
        original_price = cls._extract_original_price(combined_text, selling_price=price)

        # 4. Extract Brand and Model
        brand, model = cls._extract_brand_model(cleaned_name)

        # 5. Extract Rating and Review Count (strictly None if not found)
        rating, review_count = cls._extract_rating_reviews(raw.snippet)

        # 6. Extract Availability
        availability = cls._extract_availability(raw.snippet)

        # 7. Extract Specifications
        specifications = cls._extract_specifications(cleaned_name + " " + raw.snippet)

        # 8. Image verification
        verified_img = ImageVerifier.verify_image(raw.image_url)

        # 9. Source & Seller
        source = raw.source or "Web Retailer"
        seller = source

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build primary offer
        initial_offers: List[ProductOffer] = []
        if original_price is not None:
            specifications["original_price"] = original_price

        if price is not None:
            initial_offers.append(
                ProductOffer(
                    platform=source,
                    seller=seller,
                    price=price,
                    original_price=original_price,
                    currency=currency,
                    availability=availability if availability is not None else True,
                    delivery=cls._extract_delivery(raw.snippet),
                    url=verified_url,
                    image_url=verified_img,
                    observed_at=now_iso,
                    verification_status=status,
                    supported_actions=["view_product", "add_to_cart", "buy_now"],
                )
            )

        return Product(
            product_name=cleaned_name,
            brand=brand,
            model=model,
            price=price,
            currency=currency,
            rating=rating,
            review_count=review_count,
            seller=seller,
            availability=availability,
            delivery=cls._extract_delivery(raw.snippet),
            return_policy=cls._extract_return_policy(raw.snippet),
            specifications=specifications,
            url=verified_url,
            image_url=verified_img,
            source=source,
            source_url=verified_url,
            relevance_score=1.0,
            is_exact_match=True,
            verification_status=status,
            observed_at=now_iso,
            last_verified_at=now_iso,
            offers=initial_offers,
        )

    @staticmethod
    def _clean_title(title: str) -> str:
        """Strip store suffixes, promotional tags, and SEO junk from titles."""
        # e.g., "Redmi Note 10S (Frost White, 64 GB) (6 GB RAM) - Flipkart"
        t = re.sub(r"\s*[-|–—:]\s*(Amazon\.in|Flipkart\.com|Croma|Reliance Digital|Myntra|Ajio|Buy Online.*)$", "", title, flags=re.IGNORECASE)
        t = re.sub(r"(?:Buy\s+|Online at Best Price.*)", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip(" -|:")
        return t

    @staticmethod
    def _extract_price(text: Optional[str]) -> Optional[float]:
        """Extract numeric price from text. Returns None if unknown."""
        price, _ = ProductPageExtractor._extract_price_and_currency(text)
        return price

    @staticmethod
    def _extract_price_and_currency(text: Optional[str]) -> Tuple[Optional[float], str]:
        """Extract numeric price and currency. Returns (None, INR) if unknown."""
        if not text:
            return None, "INR"
        patterns = [
            (r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)", "INR"),
            (r"(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)", "USD"),
            (r"(?:price|starting at|deal price|cost)\s*[:=]?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)", "INR"),
        ]
        clean_text = re.sub(r"\b\d+\s*(?:mah|px|cm|mm|hz|watt|w|gb|tb|mp|inch|inches)\b", "", text, flags=re.IGNORECASE)
        for pattern, currency in patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                try:
                    raw_val = match.group(1).replace(",", "")
                    val = float(raw_val)
                    if 2020 <= val <= 2035 and "₹" not in text and "rs" not in text.lower() and "$" not in text:
                        continue
                    if 1 <= val <= 2000000:
                        return val, currency
                except ValueError:
                    pass
        return None, "INR"

    @staticmethod
    def _extract_original_price(text: Optional[str], selling_price: Optional[float] = None) -> Optional[float]:
        """Extract MRP/original price only when explicitly present in source text."""
        if not text:
            return None
        patterns = [
            r"(?:M\.?R\.?P\.?|was|list price|original(?:\s*price)?)\s*[:=]?\s*(?:₹|Rs\.?|INR|USD|US\$|\$)?\s*([\d,]+(?:\.\d{1,2})?)",
            r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:M\.?R\.?P\.?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            try:
                val = float(match.group(1).replace(",", ""))
                if val < 1 or val > 2000000:
                    continue
                if selling_price is not None and val <= selling_price:
                    continue
                return val
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_brand_model(name: str) -> Tuple[Optional[str], Optional[str]]:
        known_brands = [
            "Apple", "Samsung", "Xiaomi", "Redmi", "OnePlus", "Realme", "Google", "Sony",
            "Nike", "Adidas", "Puma", "Reebok", "Boat", "JBL", "Noise", "Fire-Boltt",
            "HP", "Lenovo", "Dell", "Asus", "Acer", "LG", "Canon", "Nikon", "Arduino",
            "Whirlpool", "Bosch", "Philips", "Casio", "Titan", "Fastrack"
        ]
        brand = None
        for b in known_brands:
            if re.search(rf"\b{b}\b", name, re.IGNORECASE):
                brand = b
                break

        # Model extraction heuristic: word sequence after brand
        model = None
        if brand:
            pattern = rf"\b{brand}\b\s+([A-Za-z0-9\s+]+?)(?:\s*\(|\s*,|\s*-|$)"
            m = re.search(pattern, name, re.IGNORECASE)
            if m:
                model = m.group(1).strip()[:50]

        return brand, model

    @staticmethod
    def _extract_rating_reviews(text: str) -> Tuple[Optional[float], Optional[int]]:
        """Extract rating and review count. Returns (None, None) if not explicitly present."""
        rating = None
        review_count = None

        if not text:
            return None, None

        # Rating: 4.3 out of 5, 4.3/5, 4.3 stars, ⭐ 4.3
        rate_m = re.search(r"(\b[1-5]\.[0-9]\b)(?:\s*(?:out of 5|\/5|stars|★|⭐))?", text)
        if rate_m:
            try:
                r = float(rate_m.group(1))
                if 1.0 <= r <= 5.0:
                    rating = r
            except Exception:
                pass

        # Reviews: 1,420 reviews, 500 ratings
        rev_m = re.search(r"([\d,]+)\s*(?:reviews|ratings|customer reviews)", text, re.IGNORECASE)
        if rev_m:
            try:
                rc = int(rev_m.group(1).replace(",", ""))
                review_count = rc
            except Exception:
                pass

        return rating, review_count

    @staticmethod
    def _extract_availability(text: str) -> Optional[bool]:
        """Returns True if in stock, False if out of stock, None if unknown."""
        if not text:
            return None
        lower = text.lower()
        if any(x in lower for x in ["out of stock", "sold out", "currently unavailable"]):
            return False
        if any(x in lower for x in ["in stock", "available", "buy now", "ready to ship"]):
            return True
        return None

    @staticmethod
    def _extract_delivery(text: str) -> Optional[str]:
        if not text:
            return None
        m = re.search(r"(free delivery|delivery by [A-Za-z0-9\s]+|fast delivery|standard delivery|\d+-\d+ days delivery)", text, re.IGNORECASE)
        return m.group(1).capitalize() if m else None

    @staticmethod
    def _extract_return_policy(text: str) -> Optional[str]:
        if not text:
            return None
        m = re.search(r"(\d+\s*days?\s*returns?|replacement policy|easy return)", text, re.IGNORECASE)
        return m.group(1).capitalize() if m else None

    @staticmethod
    def _extract_specifications(text: str) -> Dict[str, Any]:
        specs: Dict[str, Any] = {}
        # RAM
        ram_m = re.search(r"(\d+\s*(?:GB|TB))\s*RAM", text, re.IGNORECASE)
        if ram_m:
            specs["RAM"] = ram_m.group(1).upper()

        # Storage / ROM
        rom_m = re.search(r"(\d+\s*(?:GB|TB))\s*(?:ROM|Storage|SSD|HDD)", text, re.IGNORECASE)
        if rom_m:
            specs["Storage"] = rom_m.group(1).upper()

        # Display size
        disp_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:inch|\"|cm)\s*(?:display|screen|tv|4k)?", text, re.IGNORECASE)
        if disp_m:
            specs["Screen Size"] = f"{disp_m.group(1)} inch"

        # Resolution
        if re.search(r"\b4K\b|Ultra HD|3840x2160", text, re.IGNORECASE):
            specs["Resolution"] = "4K Ultra HD"
        elif re.search(r"\bFull HD\b|1080p|1920x1080", text, re.IGNORECASE):
            specs["Resolution"] = "Full HD"

        return specs
