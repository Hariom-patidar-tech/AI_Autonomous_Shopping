from __future__ import annotations
import logging
import re
from typing import List, Dict, Any
from backend.schemas.product import Product, ProductOffer

logger = logging.getLogger("shopping_agent.matcher")

COLORS = {
    "black", "white", "blue", "red", "green", "pink", "silver", "gold", "gray",
    "grey", "yellow", "orange", "purple", "midnight", "starlight", "rose", "beige",
}

STORAGE_PATTERNS = [
    r"\b(\d+)\s*(?:gb|tb)\b",
]

RAM_PATTERNS = [
    r"\b(\d+)\s*gb\s*ram\b",
]

SIZE_PATTERNS = [
    r"\b(\d{1,2}(?:\.\d+)?)\s*(?:inch|\"|mm)\b",
]


class ProductMatcher:
    """
    Detects and matches the same product across Amazon, Flipkart, and other retailers.
    Crucially variant-aware:
    - Matches same brand, model, and matching variant
    - Does NOT merge different storage, RAM, size, or color variants.
    """

    @classmethod
    def match_and_merge(cls, products: List[Product]) -> List[Product]:
        """
        Group same products across retailers into single Product with multi-platform offers.
        """
        merged_products: List[Product] = []

        for p in products:
            matched_existing = None
            p_sig = cls.extract_signature(p)

            for existing in merged_products:
                existing_sig = cls.extract_signature(existing)
                if cls.is_same_product(p_sig, existing_sig):
                    matched_existing = existing
                    break

            if matched_existing:
                cls._merge_product_offers(matched_existing, p)
            else:
                # Clone offers if not present
                if not p.offers and p.price and p.url:
                    p.offers = [
                        ProductOffer(
                            platform=p.source,
                            seller=p.seller or p.source,
                            price=p.price,
                            currency=p.currency,
                            availability=p.availability,
                            delivery=p.delivery,
                            url=p.url,
                            image_url=p.image_url,
                            observed_at=p.observed_at,
                            verification_status=p.verification_status,
                        )
                    ]
                merged_products.append(p)

        logger.info(f"ProductMatcher: {len(products)} products matched down to {len(merged_products)} unique items.")
        return merged_products

    @classmethod
    def extract_signature(cls, p: Product) -> Dict[str, Any]:
        """Extract canonical matching attributes from a product."""
        name_lower = p.product_name.lower()
        brand = (p.brand or "").strip().lower()
        model = (p.model or "").strip().lower()

        # If brand not specified, extract known brand from title
        if not brand:
            for b in ["apple", "samsung", "boat", "noise", "boult", "fire-boltt", "ptron", "sony", "xiaomi", "redmi", "titan", "fastrack", "casio"]:
                if re.search(rf"\b{re.escape(b)}\b", name_lower):
                    brand = b
                    break

        # Extract color
        tokens = set(re.findall(r"\b[a-z0-9]+\b", name_lower))
        color_found = tokens & COLORS
        color = sorted(color_found)[0] if color_found else None

        # Extract storage
        storage = None
        for pat in STORAGE_PATTERNS:
            m = re.search(pat, name_lower)
            if m:
                storage = m.group(0).replace(" ", "")
                break

        # Extract size
        size = None
        for pat in SIZE_PATTERNS:
            m = re.search(pat, name_lower)
            if m:
                size = m.group(0).replace(" ", "")
                break

        # Clean title tokens for core model identity
        stop_words = {
            "new", "original", "official", "buy", "online", "price", "sale", "deal",
            "smartwatch", "smart", "watch", "calling", "bluetooth", "display", "hd",
            "with", "for", "the", "and", "edition", "pro", "plus", "max", "ultra",
            "amazon", "flipkart", "croma", "boAt", "noise",
        }
        name_tokens = [w for w in re.findall(r"\b[a-z0-9]+\b", name_lower) if w not in stop_words]

        return {
            "brand": brand,
            "model": model,
            "color": color,
            "storage": storage,
            "size": size,
            "core_tokens": set(name_tokens),
            "raw_name": name_lower,
        }

    @classmethod
    def is_same_product(cls, sig1: Dict[str, Any], sig2: Dict[str, Any]) -> bool:
        """Determines if two product signatures represent the exact same product."""
        # 1. Brand must match if both present
        if sig1["brand"] and sig2["brand"] and sig1["brand"] != sig2["brand"]:
            return False

        # 2. Variants must NOT conflict
        # Storage conflict check (e.g. 64GB vs 128GB)
        if sig1["storage"] and sig2["storage"] and sig1["storage"] != sig2["storage"]:
            return False

        # Size conflict check (e.g. 40mm vs 44mm or 55 inch vs 65 inch)
        if sig1["size"] and sig2["size"] and sig1["size"] != sig2["size"]:
            return False

        # Color conflict check (e.g. Black vs Silver)
        if sig1["color"] and sig2["color"] and sig1["color"] != sig2["color"]:
            return False

        # 3. Model check
        if sig1["model"] and sig2["model"]:
            if sig1["model"] == sig2["model"]:
                return True

        # 4. Token overlap check for core model tokens
        tokens1 = sig1["core_tokens"]
        tokens2 = sig2["core_tokens"]
        if tokens1 and tokens2:
            intersection = tokens1 & tokens2
            union = tokens1 | tokens2
            jaccard = len(intersection) / len(union)
            # High lexical similarity on model keywords
            if jaccard >= 0.70:
                return True

        return False

    @classmethod
    def _merge_product_offers(cls, target: Product, source: Product):
        """Merge offers from source product into target product, tracking best price."""
        existing_keys = {
            (o.platform.lower(), (o.seller or "").lower(), o.url.lower(), o.price, o.currency.upper())
            for o in target.offers
        }

        # Source offers to merge
        source_offers = source.offers if source.offers else [
            ProductOffer(
                platform=source.source,
                seller=source.seller or source.source,
                price=source.price,
                currency=source.currency,
                availability=source.availability,
                delivery=source.delivery,
                url=source.url,
                image_url=source.image_url,
                observed_at=source.observed_at,
                verification_status=source.verification_status,
            )
        ]

        for off in source_offers:
            key = (off.platform.lower(), (off.seller or "").lower(), off.url.lower(), off.price, off.currency.upper())
            if key not in existing_keys:
                target.offers.append(off)
                existing_keys.add(key)
                logger.info(f"Merged offer from '{off.platform}' into product '{target.product_name}'")

        # Sort offers by price ascending
        target.offers.sort(key=lambda o: (o.price if o.price is not None else float("inf")))

        # Update primary product attributes to the best (lowest) price offer
        if target.offers:
            best_offer = target.offers[0]
            if best_offer.price is not None and (target.price is None or best_offer.price < target.price):
                target.price = best_offer.price
                target.currency = best_offer.currency
                target.source = best_offer.platform
                target.url = best_offer.url
                target.source_url = best_offer.url
                target.seller = best_offer.seller
                if best_offer.image_url and not target.image_url:
                    target.image_url = best_offer.image_url
