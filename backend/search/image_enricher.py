from __future__ import annotations
import asyncio
import json
import logging
import re
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from backend.schemas.product import Product
from backend.search.verifier import ImageVerifier

logger = logging.getLogger("shopping_agent.search.image_enricher")


class ImageEnricher:
    """
    Asynchronously retrieves and attaches verified live product images for extracted products
    using live retail image search endpoints.
    """

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    }

    @classmethod
    async def fetch_product_image(cls, client: httpx.AsyncClient, query: str) -> Optional[str]:
        """Fetch live verified product image URL for a specific product query."""
        try:
            url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}"
            resp = await client.get(url, timeout=3.5)
            if resp.status_code == 200:
                return cls._select_relevant_image(resp.text, query)
        except Exception as exc:
            logger.debug(f"Live image fetch failed for '{query}': {exc}")
        return None

    @classmethod
    def _select_relevant_image(cls, html: str, query: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for result in soup.select("a.iusc[m]"):
            try:
                metadata = json.loads(result.get("m", "{}"))
            except (TypeError, json.JSONDecodeError):
                continue

            title = metadata.get("t", "")
            image_url = metadata.get("murl", "")
            if cls._image_title_matches(query, title):
                verified = ImageVerifier.verify_image(image_url)
                if verified:
                    return verified
        return None

    @staticmethod
    def _image_title_matches(query: str, title: str) -> bool:
        ignored_terms = {
            "buy", "price", "online", "india", "review", "reviews", "official",
            "amazon", "flipkart", "croma", "walmart", "bestbuy", "ebay",
        }
        query_terms = {
            term for term in re.findall(r"[a-z0-9]+", query.lower())
            if term not in ignored_terms
        }
        title_terms = set(re.findall(r"[a-z0-9]+", title.lower()))
        required_matches = 1 if len(query_terms) == 1 else 2
        return len(query_terms & title_terms) >= required_matches

    @classmethod
    async def enrich_products(cls, products: List[Product], limit: Optional[int] = None) -> List[Product]:
        """
        Concurrently enriches products that lack verified images.
        Enforces 0% fake data: returns None if no verified real image is retrieved.
        """
        tasks = []
        indices_to_enrich = []

        async with httpx.AsyncClient(headers=cls._HEADERS, follow_redirects=True) as client:
            candidates = products if limit is None else products[:limit]
            for idx, p in enumerate(candidates):
                if not p.image_url:
                    query_term = f"{p.product_name} {p.brand or ''} {p.source or ''}".strip()
                    tasks.append(cls.fetch_product_image(client, query_term))
                    indices_to_enrich.append(idx)

            if not tasks:
                return products

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, res in zip(indices_to_enrich, results):
                if isinstance(res, str) and res.startswith("http"):
                    products[idx].image_url = res
                    # Update primary offer image as well
                    if products[idx].offers:
                        for off in products[idx].offers:
                            if not off.image_url:
                                off.image_url = res

        return products
