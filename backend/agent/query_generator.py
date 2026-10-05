from __future__ import annotations
import logging
from typing import List
from backend.schemas.query import ShoppingRequirements

logger = logging.getLogger("shopping_agent.query_generator")

MAJOR_RETAILER_SITES = (
    "site:amazon.in OR site:amazon.com OR site:flipkart.com OR site:croma.com "
    "OR site:reliancedigital.in OR site:walmart.com OR site:bestbuy.com OR site:ebay.com "
    "OR site:target.com OR site:boat-lifestyle.com OR site:gonoise.com OR site:meesho.com "
    "OR site:nykaa.com OR site:apple.com OR site:samsung.com"
)


class QueryGenerator:
    """
    Generates 3-5 focused, high-intent e-commerce search queries based on structured requirements.
    Avoids broad or irrelevant queries.
    """

    @classmethod
    def generate_focused_queries(cls, req: ShoppingRequirements) -> List[str]:
        queries: List[str] = []
        raw = req.raw_query.strip()

        # If it's an exact model search (e.g. Redmi Note 10S, iPhone 17 Pro)
        if req.brand and req.model:
            base_model = f"{req.brand} {req.model}".strip()
            queries.append(base_model)
            queries.append(f'"{base_model}" ({MAJOR_RETAILER_SITES})')
            queries.append(f"{base_model} price")
            queries.append(f"{base_model} buy online")
            return queries

        # If category and keywords exist (e.g. cat logo t-shirt)
        if req.keywords and len(req.keywords) > 0:
            core_kw = " ".join(req.keywords)
            queries.append(f"{core_kw} buy online")
            queries.append(f'"{core_kw}" ({MAJOR_RETAILER_SITES})')
            queries.append(f"{core_kw} price")
            if req.product_type and req.product_type not in core_kw:
                queries.append(f"{core_kw} {req.product_type}")
            else:
                queries.append(f"{core_kw} online shopping")

        # Add budget constraint to search query if specified
        if req.budget_max and len(queries) < 4:
            base = queries[0] if queries else raw
            queries.append(f"{base} under {int(req.budget_max)}")

        # Ensure original clean query is included
        if raw not in queries:
            queries.insert(0, raw)

        # Deduplicate while preserving order
        unique_queries = []
        for q in queries:
            if q not in unique_queries:
                unique_queries.append(q)

        logger.info(f"Generated focused search queries: {unique_queries[:4]}")
        return unique_queries[:4]
