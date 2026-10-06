from __future__ import annotations
import asyncio
import logging
import time
from typing import List, Optional, Any
from urllib.parse import urlparse
import httpx

from google import genai
from google.genai import types

from backend.config import settings
from backend.search.base import RawSearchResult
from backend.search.product_page_verifier import ProductPageVerifier
from backend.search.verifier import URLVerifier
from providers.base import BaseProvider, NormalizedProduct

logger = logging.getLogger("shopping_agent.providers.google_search")


class GoogleSearchProvider(BaseProvider):
    """
    Google Web Search Grounding provider.
    Acts as discovery / fallback provider.
    Gracefully handles HTTP 429 (Resource Exhausted) without crashing.
    """
    _quota_exhausted: bool = False
    _quota_retry_after: float = 0.0
    _quota_cooldown_seconds: float = 300.0

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._client = None
        self.last_error: Optional[str] = None
        if self._api_key:
            try:
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI client: {e}")
                self.last_error = str(e)

    @property
    def name(self) -> str:
        return "Google Search Grounding"

    @classmethod
    def quota_cooldown_remaining(cls) -> int:
        return max(0, int(cls._quota_retry_after - time.monotonic()))

    @classmethod
    def is_quota_exhausted(cls) -> bool:
        return cls._quota_exhausted and cls.quota_cooldown_remaining() > 0

    async def is_available(self) -> bool:
        if GoogleSearchProvider._quota_exhausted:
            if GoogleSearchProvider.quota_cooldown_remaining() > 0:
                return False
            GoogleSearchProvider._quota_exhausted = False
        return bool(self._api_key and self._client)

    def get_status_message(self) -> str:
        if GoogleSearchProvider.is_quota_exhausted():
            rem = GoogleSearchProvider.quota_cooldown_remaining()
            return f"Google Search quota exhausted (HTTP 429, retry in {rem}s)"
        if self.last_error:
            return f"Google Search error: {self.last_error}"
        if not self._api_key:
            return "Google Search API key not configured"
        return "Google Search ready"

    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Execute Google Search Grounding with graceful 429 handling."""
        if not await self.is_available():
            logger.info("Google Search skipped: unavailable or active cooldown.")
            return []

        prompt = (
            f"Search Google for current product pages and prices for: '{query}'.\n"
            "Prefer product detail pages on Amazon.in, Flipkart.com, Croma.com, RelianceDigital.in, TataCLiQ.com.\n"
            "Return only verified product pages with name, price, and exact URL."
        )

        candidates: List[RawSearchResult] = []
        try:
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

            for chunk in grounding_chunks:
                if chunk.web and chunk.web.uri:
                    uri = chunk.web.uri
                    title = chunk.web.title or query
                    domain = ""
                    try:
                        domain = urlparse(uri).netloc.lower().replace("www.", "")
                    except Exception:
                        pass

                    source = "Web"
                    if "amazon" in domain:
                        source = "Amazon"
                    elif "flipkart" in domain:
                        source = "Flipkart"
                    elif "croma" in domain:
                        source = "Croma"
                    elif "reliancedigital" in domain:
                        source = "Reliance Digital"

                    candidates.append(
                        RawSearchResult(
                            title=title,
                            snippet=f"Live result for {title}",
                            url=uri,
                            source=source,
                            domain=domain,
                        )
                    )

        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                GoogleSearchProvider._quota_exhausted = True
                GoogleSearchProvider._quota_retry_after = time.monotonic() + GoogleSearchProvider._quota_cooldown_seconds
                self.last_error = "Google Search API quota exhausted (HTTP 429)"
                logger.warning("Google Search quota exhausted (HTTP 429); continuing with other providers.")
            else:
                self.last_error = err_str
                logger.error(f"GoogleSearchProvider error on '{query}': {exc}")
            return []

        # Verify candidate pages concurrently with httpx
        valid_candidates = [c for c in candidates if URLVerifier.is_product_page_url(c.url)][:limit * 2]
        if not valid_candidates:
            return []

        verified_products: List[NormalizedProduct] = []
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
            timeout=8.0,
        ) as client:
            tasks = [ProductPageVerifier.verify(cand, client) for cand in valid_candidates]
            verified_results = await asyncio.gather(*tasks, return_exceptions=True)
            for cand, verified in zip(valid_candidates, verified_results):
                if isinstance(verified, Exception) or not verified:
                    continue
                if verified.price and verified.price > 0 and verified.image_url:
                    verified_products.append(
                        NormalizedProduct(
                            product_id=verified.url,
                            name=verified.product_name,
                            brand=verified.brand,
                            model=verified.model,
                            variant=None,
                            price=verified.price,
                            currency=verified.currency or "INR",
                            thumbnail=verified.image_url,
                            retailer=verified.source or cand.source,
                            product_url=verified.url,
                            availability=verified.availability if verified.availability is not None else True,
                            verified=True,
                        )
                    )
                if len(verified_products) >= limit:
                    break

        logger.info(f"Google Search produced {len(verified_products)} page-verified products.")
        return verified_products
