from __future__ import annotations
import asyncio
import logging
from typing import List, Tuple
import httpx
from backend.search.base import SearchProvider, RawSearchResult
from backend.search.google_provider import GoogleSearchProvider
from backend.search.web_provider import WebSearchProvider
from backend.search.extractor import CandidateDetector, ProductPageExtractor
from backend.search.product_page_verifier import ProductPageVerifier
from backend.schemas.product import Product
from backend.schemas.query import ShoppingRequirements

logger = logging.getLogger("shopping_agent.search.orchestrator")


class SearchOrchestrator:
    """
    Coordinates multi-source live web product searches:
    Primary (Google Search Grounding) -> Secondary (Web Search Discovery).
    Never uses mock data, dummy data, or static catalogs.
    Never invents fake products or fake URLs.
    """

    def __init__(self, primary_provider: SearchProvider = None, secondary_provider: SearchProvider = None):
        self.primary_provider = primary_provider or GoogleSearchProvider()
        self.secondary_provider = secondary_provider or WebSearchProvider()

    async def execute_search(
        self,
        primary_query: str,
        focused_queries: List[str],
        requirements: ShoppingRequirements,
        limit: int = 12,
    ) -> Tuple[List[Product], List[str], str, bool]:
        """
        Executes live search queries across real web providers.
        Returns: (extracted_products, sources_used, data_source, provider_error)
        data_source is ALWAYS 'live'.
        """
        all_raw_results: List[RawSearchResult] = []
        sources_used: List[str] = []
        data_source = "live"
        provider_error = False

        queries_to_run = [primary_query]
        for q in focused_queries:
            if q not in queries_to_run and len(queries_to_run) < 4:
                queries_to_run.append(q)

        logger.info(f"Orchestrating live search across queries: {queries_to_run}")

        # 1. Search Google, then verify every candidate against its retailer page.
        primary_success = False
        if await self.primary_provider.is_available():
            try:
                res = await self.primary_provider.search(
                    query=primary_query,
                    limit=limit,
                    additional_queries=focused_queries,
                )
                if res:
                    all_raw_results.extend(res)
                    sources_used.append("Google Search Grounding")
                primary_success = True
            except Exception as e:
                logger.warning(f"Primary Google Search Grounding provider error: {e}")
                provider_error = True
        else:
            logger.info("Primary search provider not configured or available.")

        verified_products: List[Product] = []
        seen_urls: set[str] = set()
        minimum_verified_offers = min(4, limit)

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NexShop/1.0; +https://localhost)",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
            timeout=httpx.Timeout(10.0, connect=5.0),
        ) as client:
            semaphore = asyncio.Semaphore(6)

            async def verify_candidates(candidates: List[RawSearchResult]) -> List[Product]:
                new_candidates = []
                for candidate in candidates:
                    clean_url = candidate.url.strip()
                    if clean_url and clean_url not in seen_urls:
                        seen_urls.add(clean_url)
                        if CandidateDetector.is_candidate(candidate):
                            new_candidates.append(candidate)

                async def verify_one(candidate: RawSearchResult) -> Product | None:
                    async with semaphore:
                        return await ProductPageVerifier.verify(candidate, client)

                checked = await asyncio.gather(
                    *(verify_one(candidate) for candidate in new_candidates),
                    return_exceptions=True,
                )
                return [item for item in checked if isinstance(item, Product)]

            verified_products.extend(await verify_candidates(all_raw_results))

            # Continue searching retailer-focused queries until enough real offers verify.
            secondary_success = False
            if len(verified_products) < minimum_verified_offers and await self.secondary_provider.is_available():
                logger.info("Google yielded fewer than %s verified offers; continuing with web search.", minimum_verified_offers)
                for query in queries_to_run[:4]:
                    try:
                        results = await self.secondary_provider.search(query, limit=limit)
                        secondary_success = True
                        if results:
                            all_raw_results.extend(results)
                            if "Web Search Provider" not in sources_used:
                                sources_used.append("Web Search Provider")
                            verified_products.extend(await verify_candidates(results))
                        if len(verified_products) >= minimum_verified_offers:
                            break
                    except Exception as exc:
                        logger.warning("Secondary live search failed for query '%s': %s", query, exc)
                        provider_error = True

        if not primary_success and not secondary_success and provider_error:
            logger.error("All real search providers encountered errors.")

        logger.info(
            "Live search completed: %s page-verified offers from real retailer product pages.",
            len(verified_products),
        )
        return verified_products, list(set(sources_used)), data_source, provider_error
