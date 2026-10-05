from __future__ import annotations
import re
import logging
from typing import List
from backend.schemas.product import Product

logger = logging.getLogger("shopping_agent.deduplicator")


class Deduplicator:
    """
    Deduplicates products across search queries and providers.
    Crucially variant-aware: does NOT merge 64GB with 128GB or different colors/sizes.
    """

    @classmethod
    def deduplicate(cls, products: List[Product]) -> List[Product]:
        unique_products: List[Product] = []
        seen_keys = set()

        for p in products:
            variant_key = cls._compute_variant_key(p)
            if variant_key not in seen_keys:
                seen_keys.add(variant_key)
                unique_products.append(p)
            else:
                # Merge offers into existing product if from different sellers
                for existing in unique_products:
                    if cls._compute_variant_key(existing) == variant_key:
                        cls._merge_offers(existing, p)
                        break

        logger.info(f"Deduplication: {len(products)} -> {len(unique_products)} unique products.")
        return unique_products

    @classmethod
    def _compute_variant_key(cls, p: Product) -> str:
        name = p.product_name.lower()
        tokens = set(re.findall(r"[a-z0-9]+", name))
        brand_tokens = set(re.findall(r"[a-z0-9]+", (p.brand or "").lower()))
        model_tokens = set(re.findall(r"[a-z0-9]+", (p.model or "").lower()))
        generic_terms = {
            "new", "original", "official", "buy", "online", "price", "sale", "deal",
            "india", "usa", "amazon", "flipkart", "croma", "walmart", "ebay", "bestbuy",
            "wireless", "bluetooth", "true", "tws", "earbuds", "earbud", "earphones",
            "earphone", "headphones", "headphone", "noise", "cancellation", "canceling",
            "with", "for", "the", "and",
        }
        identity = sorted(token for token in tokens if token not in generic_terms and not token.isdigit())
        variants = sorted(token for token in tokens if any(char.isdigit() for char in token))
        if model_tokens:
            colors = {"black", "white", "blue", "red", "green", "pink", "silver", "gold", "gray", "grey"}
            variant_tokens = variants + sorted(tokens & colors)
            identity = sorted(brand_tokens | model_tokens)
            variants = variant_tokens
        return "|".join(identity + ["#"] + variants)

    @classmethod
    def _merge_offers(cls, target: Product, source: Product):
        """Merge newly discovered offers from another platform into the product."""
        existing_offers = {
            (o.platform.lower(), (o.seller or "").lower(), o.url.lower(), o.price, o.currency.upper())
            for o in target.offers
        }
        for off in source.offers:
            offer_key = (off.platform.lower(), (off.seller or "").lower(), off.url.lower(), off.price, off.currency.upper())
            if offer_key not in existing_offers:
                target.offers.append(off)
                existing_offers.add(offer_key)
                logger.info(f"Added multi-platform offer '{off.platform}' to product '{target.product_name}'")
