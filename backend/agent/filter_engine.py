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
            if req.budget_max is not None or req.budget_min is not None:
                if p.offers:
                    eligible_offers = [
                        offer for offer in p.offers
                        if offer.currency.upper() == req.currency.upper()
                        and (req.budget_max is None or offer.price <= req.budget_max)
                        and (req.budget_min is None or offer.price >= req.budget_min)
                    ]
                    if not eligible_offers:
                        rejections.append({
                            "product": p.product_name,
                            "reason": "No verified offer matches the requested currency and budget",
                        })
                        continue
                    p.offers = eligible_offers
                    best_offer = min(eligible_offers, key=lambda offer: offer.price)
                    p.price = best_offer.price
                    p.currency = best_offer.currency
                    p.source = best_offer.platform
                    p.url = best_offer.url
                    p.source_url = best_offer.url
                    p.seller = best_offer.seller
                    p.image_url = best_offer.image_url or p.image_url
                    p.availability = best_offer.availability
                else:
                    if p.price is None:
                        rejections.append({
                            "product": p.product_name,
                            "reason": "Price is unavailable; cannot verify the requested budget",
                        })
                        continue
                    if p.currency.upper() != req.currency.upper():
                        rejections.append({
                            "product": p.product_name,
                            "reason": f"Price currency {p.currency} does not match requested currency {req.currency}",
                        })
                        continue

            # 1. Budget Max Filter (Deterministic)
            if req.budget_max is not None:
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
