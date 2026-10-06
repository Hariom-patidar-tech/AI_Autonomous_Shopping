from __future__ import annotations
import logging
import time
from typing import List, Optional
from urllib.parse import urlparse
from google import genai
from google.genai import types
from backend.config import settings
from backend.search.base import SearchProvider, RawSearchResult

logger = logging.getLogger("shopping_agent.search.google")


class GoogleSearchProvider(SearchProvider):
    """
    Official Google Web Search Provider using Gemini 2.5 Flash Google Search Grounding.
    Executes live Google web searches and extracts real web sources, verified URLs, titles, and price data.
    """
    _quota_exhausted: bool = False
    _quota_retry_after: float = 0.0
    _quota_cooldown_seconds: float = 300.0

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._client = None
        if self._api_key:
            try:
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI client: {e}")

    @property
    def name(self) -> str:
        return "GoogleSearchGrounding"

    @classmethod
    def quota_cooldown_remaining(cls) -> int:
        return max(0, int(cls._quota_retry_after - time.monotonic()))

    @classmethod
    def quota_exhausted(cls) -> bool:
        return cls._quota_exhausted and cls.quota_cooldown_remaining() > 0

    async def is_available(self) -> bool:
        if GoogleSearchProvider._quota_exhausted:
            if GoogleSearchProvider.quota_cooldown_remaining() > 0:
                return False
            GoogleSearchProvider._quota_exhausted = False
        return bool(self._api_key and self._client)

    async def search(self, query: str, limit: int = 10, additional_queries: Optional[List[str]] = None) -> List[RawSearchResult]:
        if not await self.is_available():
            logger.warning("Google search provider is unavailable (missing key or active quota cooldown).")
            return []

        queries_text = f"'{query}'"
        if additional_queries:
            clean_add = [q for q in additional_queries if q.lower() != query.lower()]
            if clean_add:
                queries_text += f" (and retailer-focused queries: {', '.join(clean_add[:8])})"

        prompt = (
            f"Search Google for current purchasing listings and retail prices for: {queries_text}.\n"
            "Prefer canonical product pages on Amazon, Flipkart, Croma, Reliance Digital, Walmart, Best Buy, eBay.\n"
            "Use queries like: \"{query}\" (site:amazon.in OR site:flipkart.com OR site:croma.com).\n"
            "List specific products found with:\n"
            "- Exact Product Name / Title (matching the requested model/variant)\n"
            "- Retailer/Store\n"
            "- Current selling price with currency\n"
            "- Original MRP if shown (do not invent MRP)\n"
            "- Rating and review count if available\n"
            "- Stock status and delivery info if available\n"
            "- Direct product page URL\n"
            "Skip accessories, cases, and mismatched variants. Only return factual live-search information."
        )

        results: List[RawSearchResult] = []
        try:
            # Execute Gemini call with Google Search Tool Grounding
            response = self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.1,
                ),
            )

            grounding_chunks = []
            if response.candidates and response.candidates[0].grounding_metadata:
                gm = response.candidates[0].grounding_metadata
                grounding_chunks = gm.grounding_chunks or []
                logger.info(
                    f"Google Search executed queries: {gm.web_search_queries}. Grounding chunks: {len(grounding_chunks)}"
                )

            # Map grounding chunks to RawSearchResult
            for chunk in grounding_chunks:
                if chunk.web and chunk.web.uri:
                    uri = chunk.web.uri
                    title = chunk.web.title or query
                    domain = ""
                    try:
                        parsed = urlparse(uri)
                        domain = parsed.netloc.lower().replace("www.", "")
                    except Exception:
                        pass

                    source_name = domain.split(".")[0].capitalize() if domain else "Web"
                    # Determine source label
                    if "amazon" in domain:
                        source_name = "Amazon"
                    elif "flipkart" in domain:
                        source_name = "Flipkart"
                    elif "croma" in domain:
                        source_name = "Croma"
                    elif "reliancedigital" in domain:
                        source_name = "Reliance Digital"
                    elif "myntra" in domain:
                        source_name = "Myntra"
                    elif "ajio" in domain:
                        source_name = "Ajio"
                    elif "meesho" in domain:
                        source_name = "Meesho"
                    elif "tatacliq" in domain:
                        source_name = "Tata CLiQ"

                    results.append(
                        RawSearchResult(
                            title=title,
                            snippet=f"Live search result from {source_name} for {title}",
                            url=uri,
                            source=source_name,
                            domain=domain,
                        )
                    )

            logger.info(f"Google provider produced {len(results)} raw results for '{query}'.")
            return results[:limit]

        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower():
                GoogleSearchProvider._quota_exhausted = True
                GoogleSearchProvider._quota_retry_after = time.monotonic() + GoogleSearchProvider._quota_cooldown_seconds
                logger.warning("Google Search quota exhausted; falling back for %s seconds.", GoogleSearchProvider._quota_cooldown_seconds)
            else:
                logger.error(f"GoogleSearchProvider error on '{query}': {exc}")
            return []
