from __future__ import annotations
import logging
from typing import List
from backend.schemas.product import Product
from backend.schemas.query import ShoppingRequirements

logger = logging.getLogger("shopping_agent.ranking")


class RankingEngine:
    """
    Ranks filtered products based on exact relevance, specifications, user constraints,
    availability, price, rating, review count, and seller credibility.
    """

    @classmethod
    def rank(
        cls,
        products: List[Product],
        req: ShoppingRequirements,
        sort_by: str = "relevance",
    ) -> List[Product]:
        if not products:
            return []

        if sort_by == "price_asc":
            return sorted(products, key=lambda p: (p.price is None, p.price or 0))
        elif sort_by == "price_desc":
            return sorted(products, key=lambda p: (p.price is not None, p.price or 0), reverse=True)
        elif sort_by == "rating":
            return sorted(products, key=lambda p: (p.rating is not None, p.rating or 0), reverse=True)

        # Default multi-factor ranking
        def score_product(p: Product) -> float:
            score = 0.0

            # 1. Exact model / brand match priority (Section 29)
            if p.is_exact_match:
                score += 50.0

            score += p.relevance_score * 30.0

            # 2. Availability priority
            if p.availability is True:
                score += 15.0
            elif p.availability is False:
                score -= 30.0

            # 3. Rating & review signals (if available)
            if p.rating is not None:
                score += (p.rating / 5.0) * 10.0
            if p.review_count is not None and p.review_count > 100:
                score += min(p.review_count / 1000.0, 5.0)

            # 4. Price proximity to budget
            if req.budget_max and p.price:
                # Prefer reasonably priced items within budget
                if p.price <= req.budget_max:
                    score += 5.0

            # 5. Verified status
            if p.verification_status == "verified":
                score += 5.0

            return score

        ranked = sorted(products, key=score_product, reverse=True)
        logger.info(f"Ranked {len(ranked)} products by multi-factor score.")
        return ranked
