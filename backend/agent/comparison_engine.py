from __future__ import annotations
import logging
from typing import List, Optional
from backend.schemas.product import Product, PriceComparisonSummary
from backend.schemas.query import ShoppingRequirements

logger = logging.getLogger("shopping_agent.comparison")


class ComparisonEngine:
    """
    Compares verified offers across multiple shopping platforms.
    Calculates lowest price, price spread, and holistic recommendations.
    """

    @classmethod
    def generate_comparison_summary(
        cls,
        products: List[Product],
        req: ShoppingRequirements,
    ) -> Optional[PriceComparisonSummary]:
        if not products:
            return None

        # Take primary matched product
        target_product = products[0]
        currency = (target_product.currency or "INR").upper()
        all_offers = [offer for offer in target_product.offers if offer.currency.upper() == currency]

        if not all_offers:
            # Fall back across top products if individual offers list is flat
            all_offers = [
                offer for product in products[:5]
                for offer in product.offers
                if offer.price and offer.currency.upper() == currency
            ]

        if not all_offers:
            return None

        prices = [o.price for o in all_offers if o.price and o.price > 0]
        if not prices:
            return None

        lowest_price = min(prices)
        highest_price = max(prices)
        price_spread = highest_price - lowest_price

        best_offer = next((o for o in all_offers if o.price == lowest_price), all_offers[0])
        best_platform = best_offer.platform

        # Recommendation generation based on user intent
        symbol = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥"}.get(currency, f"{currency} ")
        if req.intent == "cheapest_search" or "sasta" in req.raw_query.lower() or "cheapest" in req.raw_query.lower():
            recommendation = (
                f"Lowest verified price is {symbol}{lowest_price:,.2f} on {best_platform}. "
                f"Saves you up to {symbol}{price_spread:,.2f} compared to the highest offer."
            )
        else:
            recommendation = (
                f"Best verified price is {symbol}{lowest_price:,.2f} on {best_platform}."
            )

        return PriceComparisonSummary(
            product_name=target_product.product_name,
            currency=currency,
            lowest_price=lowest_price,
            highest_price=highest_price,
            price_spread=price_spread,
            best_price_platform=best_platform,
            offers_compared=len(all_offers),
            recommendation=recommendation,
        )
