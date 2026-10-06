from __future__ import annotations
import asyncio
import base64
import logging
import os
import re
from typing import List, Optional, Any
import httpx
from bs4 import BeautifulSoup
from backend.search.base import RawSearchResult
from backend.search.product_page_verifier import ProductPageVerifier
from backend.search.verifier import URLVerifier
from providers.base import BaseProvider, NormalizedProduct

logger = logging.getLogger("shopping_agent.providers.bing_search")


class BingSearchProvider(BaseProvider):
    """
    Bing Web Search Discovery connector.
    Acts as discovery / fallback provider.
    Resolves redirect URLs to clean direct retailer pages.
    Extracts only verified price-bearing product pages.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BING_SEARCH_API_KEY", "").strip()
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
        }
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "Bing Search Discovery"

    async def is_available(self) -> bool:
        return True

    def get_status_message(self) -> str:
        if self.last_error:
            return f"Bing Search error: {self.last_error}"
        return "Bing Search Discovery ready"

    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Execute Bing search and verify discovered product pages."""
        candidates = await self._discover_candidates(query, limit=limit * 2)
        if not candidates:
            return []

        valid_candidates = [c for c in candidates if URLVerifier.is_product_page_url(c.url)][:limit * 2]
        if not valid_candidates:
            return []

        verified_products: List[NormalizedProduct] = []
        async with httpx.AsyncClient(
            headers=self._headers,
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

        logger.info(f"Bing Search produced {len(verified_products)} page-verified products.")
        return verified_products

    async def _discover_candidates(self, query: str, limit: int = 15) -> List[RawSearchResult]:
        """Fetch raw search results and exact product pages from Bing, Flipkart, and Amazon."""
        results: List[RawSearchResult] = []
        seen_urls: set[str] = set()

        # 1. Bing Live Search (filter for exact product pages)
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            async with httpx.AsyncClient(timeout=8.0, headers=self._headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for item in soup.select("li.b_algo"):
                        a_tag = item.select_one("h2 a")
                        if not a_tag or not a_tag.get("href"):
                            continue
                        title = a_tag.get_text(strip=True)
                        raw_href = a_tag["href"]
                        clean_href = self._decode_bing_redirect(raw_href)

                        domain = ""
                        try:
                            domain = urlparse(clean_href).netloc.lower().replace("www.", "")
                        except Exception:
                            pass

                        source = domain.split(".")[0].capitalize() if domain else "Web"
                        if "amazon" in domain:
                            source = "Amazon"
                        elif "flipkart" in domain:
                            source = "Flipkart"
                        elif "croma" in domain:
                            source = "Croma"
                        elif "reliancedigital" in domain:
                            source = "Reliance Digital"

                        if clean_href not in seen_urls and URLVerifier.is_product_page_url(clean_href):
                            seen_urls.add(clean_href)
                            results.append(
                                RawSearchResult(
                                    title=title,
                                    snippet=f"Discovered result for {title}",
                                    url=clean_href,
                                    source=source,
                                    domain=domain,
                                )
                            )
                elif resp.status_code == 429:
                    self.last_error = "Bing HTTP 429 rate limit"
                    logger.warning("Bing search rate-limited (HTTP 429).")
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning(f"Bing discovery search failed: {exc}")

        # 2. Direct Flipkart Search Discovery (finds exact /p/ product pages)
        try:
            fk_url = f"https://www.flipkart.com/search?q={urllib.parse.quote(query)}"
            async with httpx.AsyncClient(timeout=8.0, headers=self._headers, follow_redirects=True) as client:
                resp = await client.get(fk_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"]
                        if "/p/" in href:
                            clean_href = "https://www.flipkart.com" + href.split("?")[0] if href.startswith("/") else href.split("?")[0]
                            if clean_href not in seen_urls and URLVerifier.is_product_page_url(clean_href):
                                seen_urls.add(clean_href)
                                title = a_tag.get_text(" ", strip=True) or query
                                results.append(
                                    RawSearchResult(
                                        title=title,
                                        snippet=f"Flipkart listing for {title}",
                                        url=clean_href,
                                        source="Flipkart",
                                        domain="flipkart.com",
                                    )
                                )
        except Exception as exc:
            logger.debug(f"Flipkart candidate discovery failed: {exc}")

        # 3. Direct Amazon Search Discovery (finds exact /dp/ product pages)
        try:
            from curl_cffi import requests as c_requests
            import asyncio
            def _fetch_amz():
                return c_requests.get(
                    f"https://www.amazon.in/s?k={urllib.parse.quote(query)}",
                    impersonate="chrome",
                    timeout=8.0,
                    headers={"Accept-Language": "en-IN,en;q=0.9"},
                )
            a_resp = await asyncio.to_thread(_fetch_amz)
            if a_resp.status_code == 200:
                soup = BeautifulSoup(a_resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", a_tag["href"])
                    if m:
                        clean_href = f"https://www.amazon.in/dp/{m.group(1)}"
                        if clean_href not in seen_urls and URLVerifier.is_product_page_url(clean_href):
                            seen_urls.add(clean_href)
                            title = a_tag.get_text(" ", strip=True) or query
                            results.append(
                                RawSearchResult(
                                    title=title,
                                    snippet=f"Amazon listing for {title}",
                                    url=clean_href,
                                    source="Amazon",
                                    domain="amazon.in",
                                )
                            )
        except Exception as exc:
            logger.debug(f"Amazon candidate discovery failed: {exc}")

        return results

    def _decode_bing_redirect(self, raw_url: str) -> str:
        """Decode Bing /ck/a?! tracking URLs to destination URLs."""
        if "/ck/a?!" in raw_url and "u=" in raw_url:
            try:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                if "u" in qs:
                    u_val = qs["u"][0]
                    b64_str = u_val[2:] if len(u_val) > 2 else u_val
                    padded = b64_str + "=" * (-len(b64_str) % 4)
                    decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                    if decoded.startswith("http"):
                        return decoded
            except Exception:
                pass
        return raw_url
