from __future__ import annotations
import logging
from typing import List, Tuple
from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import Product

logger = logging.getLogger("shopping_agent.filter_engine")


class HardFilterEngine:
    """
    Applies strict, deterministic hard constraints.
    Rejects products that violate budget, rating, or in-stock requirements.
    Preserves unknown data as None without hallucinating default values.
    """

    @classmethod
    def apply_filters(
        cls,
        products: List[Product],
        req: ShoppingRequirements,
    ) -> Tuple[List[Product], List[dict]]:
        """
        Returns: (passed_products, rejection_audit_log)
        """
        passed: List[Product] = []
        rejections: List[dict] = []

        for p in products:
            # 1. Budget Max Filter (Deterministic)
            if req.budget_max is not None:
                if p.price is None:
                    rejections.append({
                        "product": p.product_name,
                        "reason": "Price is unavailable; cannot verify the maximum budget",
                    })
                    continue
                if p.price > req.budget_max:
                    rejections.append({
                        "product": p.product_name,
                        "reason": f"Price ₹{p.price:,.2f} exceeds max budget ₹{req.budget_max:,.2f}",
                    })
                    continue

            # 2. Budget Min Filter (Deterministic)
            if req.budget_min is not None and p.price is not None:
                if p.price < req.budget_min:
                    rejections.append({
                        "product": p.product_name,
                        "reason": f"Price ₹{p.price:,.2f} is below min budget ₹{req.budget_min:,.2f}",
                    })
                    continue

            # 3. Minimum Rating Filter (Deterministic)
            if req.min_rating is not None and p.rating is not None:
                if p.rating < req.min_rating:
                    rejections.append({
                        "product": p.product_name,
                        "reason": f"Rating {p.rating} is below required {req.min_rating}",
                    })
                    continue

            # 4. Out of Stock Filter
            if p.availability is False:
                rejections.append({
                    "product": p.product_name,
                    "reason": "Product is marked out of stock",
                })
                continue

            passed.append(p)

        logger.info(
            f"Hard filter applied: {len(products)} evaluated -> {len(passed)} passed, {len(rejections)} rejected."
        )
        return passed, rejections
