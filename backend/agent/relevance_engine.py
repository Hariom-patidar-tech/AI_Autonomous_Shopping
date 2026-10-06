from __future__ import annotations
import re
import logging
from typing import List, Tuple
from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import Product

logger = logging.getLogger("shopping_agent.relevance")

CATEGORY_INCOMPATIBILITIES = {
    "clothing": ["tv", "television", "phone", "smartphone", "laptop", "refrigerator", "washing machine", "lens"],
    "smartphone": ["tv", "television", "laptop", "shirt", "shoe", "refrigerator", "washing machine"],
    "laptop": ["tv", "television", "smartphone", "phone", "shirt", "shoe", "dress"],
    "television": ["laptop", "phone", "smartphone", "shoe", "shirt", "watch"],
    "shoes": ["formal", "sandal", "slipper", "watch", "phone", "laptop", "tv"],
}


TERM_SYNONYMS = {
    "smartphone": ["phone", "smartphone", "mobile", "iphone", "handset"],
    "phone": ["phone", "smartphone", "mobile", "iphone", "handset"],
    "mobile": ["phone", "smartphone", "mobile", "iphone", "handset"],
    "laptop": ["laptop", "notebook", "chromebook", "macbook", "ultrabook", "vivobook", "ideapad", "thinkpad", "zenbook"],
    "watch": ["watch", "smartwatch", "wristwatch", "timepiece"],
    "smartwatch": ["watch", "smartwatch", "wristwatch", "timepiece"],
    "earbuds": ["earbud", "earbuds", "earphone", "earphones", "airpod", "airpods", "tws", "headphone", "headphones"],
    "earbud": ["earbud", "earbuds", "earphone", "earphones", "airpod", "airpods", "tws", "headphone", "headphones"],
    "headphones": ["earbud", "earbuds", "earphone", "earphones", "airpod", "airpods", "headphone", "headphones", "headset"],
    "headphone": ["earbud", "earbuds", "earphone", "earphones", "airpod", "airpods", "headphone", "headphones", "headset"],
    "shoes": ["shoe", "shoes", "sneaker", "sneakers", "footwear", "boot", "boots", "trainer"],
    "shoe": ["shoe", "shoes", "sneaker", "sneakers", "footwear", "boot", "boots", "trainer"],
}


def _matches_keyword(kw: str, text: str) -> bool:
    syns = TERM_SYNONYMS.get(kw.lower(), [kw.lower()])
    return any(syn in text for syn in syns)


class RelevanceEngine:
    """
    Evaluates semantic and token relevance, enforces strict category mismatch protection,
    and cleanly separates Exact Matches from Alternatives.
    """

    @classmethod
    def evaluate(
        cls,
        products: List[Product],
        req: ShoppingRequirements,
    ) -> Tuple[List[Product], List[Product]]:
        """
        Returns: (exact_matches, alternatives)
        Rejects completely irrelevant products or category mismatches.
        """
        exact_matches: List[Product] = []
        alternatives: List[Product] = []

        query_lower = req.raw_query.lower()

        for p in products:
            p_name = p.product_name.lower()

            # 1. Category Mismatch Protection (Section 15)
            if not cls._passes_category_protection(p_name, req):
                logger.info(f"Category mismatch rejected: '{p.product_name}' for query '{req.raw_query}'")
                continue

            # 2. Score relevance
            score, is_exact = cls._score_relevance(p, req)
            p.relevance_score = score
            p.is_exact_match = is_exact

            if score < 0.35:
                logger.debug(f"Low relevance score ({score:.2f}) rejected: '{p.product_name}'")
                continue

            if is_exact:
                exact_matches.append(p)
            else:
                alternatives.append(p)

        logger.info(f"Relevance engine evaluated {len(products)} products -> {len(exact_matches)} exact, {len(alternatives)} alternatives.")
        return exact_matches, alternatives

    @classmethod
    def _passes_category_protection(cls, product_name: str, req: ShoppingRequirements) -> bool:
        """Enforces that unrelated categories are rejected (e.g. t-shirt query rejecting TVs)."""
        target_cat = (req.category or "").lower()
        target_type = (req.product_type or "").lower()

        if target_cat in {"headphone", "headphones"} or target_type in {"headphone", "headphones"}:
            headphone_terms = ("earbud", "earphone", "headphone", "headset", "airpod")
            if not any(term in product_name.lower() for term in headphone_terms):
                return False

            if not req.brand and not req.model:
                generic_terms = {
                    "earbud", "earbuds", "earphone", "earphones", "headphone", "headphones",
                    "headset", "airpod", "airpods", "wired", "wireless", "true", "tws",
                    "bluetooth", "noise", "cancellation", "canceling", "mic", "microphone",
                    "with", "or", "and", "in", "amazon", "flipkart", "croma", "price",
                    "buy", "online", "store", "india",
                }
                identity_terms = {
                    term for term in re.findall(r"[a-z0-9]+", product_name.lower())
                    if term not in generic_terms and not term.isdigit()
                }
                if len(identity_terms) < 2:
                    return False

        # Check explicit incompatibility list
        for cat_key, forbidden_words in CATEGORY_INCOMPATIBILITIES.items():
            if cat_key in target_cat or cat_key in target_type:
                for fw in forbidden_words:
                    if re.search(rf"\b{fw}\b", product_name, re.IGNORECASE):
                        # Ensure user didn't ask for that forbidden word
                        if fw not in req.raw_query.lower():
                            return False

        # Category-specific required keywords (Category Containment)
        lower_query = req.raw_query.lower()
        lower_pname = product_name.lower()

        if target_cat == "clothing" or "shirt" in lower_query or "t-shirt" in lower_query:
            clothing_indicators = ["t-shirt", "tshirt", "shirt", "tee", "top", "apparel", "clothing", "wear", "cotton", "polo", "hoodie"]
            if not any(ci in lower_pname for ci in clothing_indicators):
                return False

        if target_cat == "shoes" or "shoe" in lower_query:
            shoe_indicators = ["shoe", "sneaker", "boot", "footwear", "running", "trainer"]
            if not any(si in lower_pname for si in shoe_indicators):
                return False

        if target_cat in {"watch", "smartwatch"} or "watch" in lower_query or "smartwatch" in lower_query:
            if not any(acc in lower_query for acc in ["strap", "band", "cable", "charger", "guard", "cover"]):
                if any(acc in lower_pname for acc in ["strap", "watchband", "watch band", "charging cable", "screen guard", "case cover", "protective case"]):
                    return False
            watch_indicators = ["watch", "smartwatch", "dial", "timepiece"]
            if not any(wi in lower_pname for wi in watch_indicators):
                return False

        # Keyword overlap check for arbitrary products (e.g., "cat logo t-shirt")
        if req.keywords:
            meaningful_kws = [kw.lower() for kw in req.keywords if len(kw) > 2 and not kw.isdigit()]
            if meaningful_kws:
                has_keyword = any(_matches_keyword(kw, lower_pname) for kw in meaningful_kws)
                if not has_keyword:
                    cat_match = bool(target_cat and _matches_keyword(target_cat, lower_pname))
                    brand_match = bool(req.brand and req.brand.lower() in lower_pname)
                    if not (cat_match or brand_match):
                        return False

        return True

    @classmethod
    def _score_relevance(cls, product: Product, req: ShoppingRequirements) -> Tuple[float, bool]:
        name_lower = product.product_name.lower()
        score = 0.5
        is_exact = False

        # If user searched for an exact brand + model (e.g. "Redmi Note 10S")
        if req.brand and req.model:
            brand_in = req.brand.lower() in name_lower
            # Check model string with flexible spacing (e.g. Note 10S or Note 10 s)
            model_clean = re.sub(r"\s+", "", req.model.lower())
            name_nospace = re.sub(r"\s+", "", name_lower)

            if brand_in and model_clean in name_nospace:
                # Exact model match!
                score = 1.0
                is_exact = True
                return score, is_exact
            elif brand_in:
                # Same brand, different model (Alternative)
                score = 0.6
                is_exact = False
                return score, is_exact
            else:
                # Wrong brand
                return 0.2, False

        # General keyword matching with synonym support
        if req.keywords:
            meaningful_kws = [kw.lower() for kw in req.keywords if len(kw) > 2 and not kw.isdigit()]
            if meaningful_kws:
                matches = sum(1 for kw in meaningful_kws if _matches_keyword(kw, name_lower))
                ratio = matches / len(meaningful_kws)
                score = 0.4 + (ratio * 0.6)
                if ratio >= 0.75 or (len(meaningful_kws) == 1 and matches == 1):
                    is_exact = True

        return round(score, 2), is_exact
