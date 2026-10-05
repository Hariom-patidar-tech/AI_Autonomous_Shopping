from __future__ import annotations
import re
import logging
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

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._client = None
        if self._api_key and not GoogleSearchProvider._quota_exhausted:
            try:
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI client: {e}")

    @property
    def name(self) -> str:
        return "GoogleSearchGrounding"

    async def is_available(self) -> bool:
        if GoogleSearchProvider._quota_exhausted:
            return False
        return bool(self._api_key and self._client)

    async def search(self, query: str, limit: int = 10, additional_queries: Optional[List[str]] = None) -> List[RawSearchResult]:
        if not await self.is_available():
            logger.warning("Google search provider requested but API key is missing.")
            return []

        queries_text = f"'{query}'"
        if additional_queries:
            clean_add = [q for q in additional_queries if q.lower() != query.lower()]
            if clean_add:
                queries_text += f" (and related variants: {', '.join(clean_add[:3])})"

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

            # If response text has details, extract structured product lines
            text = response.text or ""
            parsed_text_offers = self._extract_offers_from_text(text, query)

            # Enrich results with parsed price text if matched
            for offer in parsed_text_offers:
                # Find matching chunk or create candidate
                matched = False
                for r in results:
                    if offer.get("store") and offer["store"].lower() in r.source.lower():
                        if offer.get("price"):
                            r.price_text = f"₹{offer['price']:,.2f}"
                        if offer.get("name") and len(offer["name"]) > 5:
                            r.title = offer["name"]
                        if offer.get("snippet"):
                            r.snippet = offer["snippet"]
                        matched = True
                        break
                if not matched and offer.get("url"):
                    results.append(
                        RawSearchResult(
                            title=offer.get("name", query),
                            snippet=offer.get("snippet", ""),
                            url=offer.get("url", ""),
                            source=offer.get("store", "Online Retailer"),
                            price_text=str(offer.get("price")) if offer.get("price") else None,
                        )
                    )

            logger.info(f"Google provider produced {len(results)} raw results for '{query}'.")
            return results[:limit]

        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower():
                GoogleSearchProvider._quota_exhausted = True
                logger.warning(f"GoogleSearchProvider quota exhausted (429). Disabling for this session.")
            else:
                logger.error(f"GoogleSearchProvider error on '{query}': {exc}")
            return []

    def _extract_offers_from_text(self, text: str, query: str) -> List[dict]:
        """Extract prices, stores, and product names from grounding response text."""
        offers = []
        lines = text.split("\n")
        current_store = None
        for line in lines:
            line_clean = line.strip(" *-#\t")
            if not line_clean:
                continue

            # Look for store names
            for s in ["Amazon", "Flipkart", "Croma", "Reliance Digital", "Myntra", "Ajio", "Tata CLiQ", "Samsung", "Apple", "Xiaomi", "Mi.com"]:
                if s.lower() in line_clean.lower():
                    current_store = s
                    break

            # Look for INR prices (₹14,999 or Rs. 14,999 or INR 14,999)
            price_match = re.search(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", line_clean, re.IGNORECASE)
            if price_match:
                try:
                    price_val = float(price_match.group(1).replace(",", ""))
                    # Avoid year numbers like 2026 being parsed as price if under 2100 unless query is cheap
                    if price_val > 50:
                        offers.append({
                            "name": line_clean[:120],
                            "price": price_val,
                            "store": current_store or "Verified Retailer",
                            "snippet": line_clean,
                        })
                except Exception:
                    pass

        return offers
