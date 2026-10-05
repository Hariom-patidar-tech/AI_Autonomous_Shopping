from __future__ import annotations
import logging
from typing import List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from backend.search.base import SearchProvider, RawSearchResult

logger = logging.getLogger("shopping_agent.search.web")


class WebSearchProvider(SearchProvider):
    """
    Direct Web Search Provider using public web search interfaces and HTML discovery.
    Acts as a reliable secondary search provider.
    """

    def __init__(self):
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
        }

    @property
    def name(self) -> str:
        return "WebSearchProvider"

    async def is_available(self) -> bool:
        return True

    async def search(self, query: str, limit: int = 10) -> List[RawSearchResult]:
        results: List[RawSearchResult] = []
        try:
            # Try DuckDuckGo HTML endpoint with httpx
            url = f"https://html.duckduckgo.com/html/?q={query}"
            async with httpx.AsyncClient(timeout=8.0, headers=self._headers, follow_redirects=True) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.select(".result__body")
                    for item in links[:limit]:
                        title_el = item.select_one(".result__title a")
                        snippet_el = item.select_one(".result__snippet")
                        if title_el and title_el.get("href"):
                            title = title_el.get_text(strip=True)
                            href = title_el.get("href")
                            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                            # Clean DDG redirect URL if present
                            if "uddg=" in href:
                                import urllib.parse
                                qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                                if "uddg" in qs:
                                    href = qs["uddg"][0]

                            domain = ""
                            try:
                                domain = urlparse(href).netloc.lower().replace("www.", "")
                            except Exception:
                                pass

                            source = domain.split(".")[0].capitalize() if domain else "Web"
                            results.append(
                                RawSearchResult(
                                    title=title,
                                    snippet=snippet,
                                    url=href,
                                    source=source,
                                    domain=domain,
                                )
                            )

            logger.info(f"WebSearchProvider (DuckDuckGo) returned {len(results)} results for '{query}'.")
        except Exception as exc:
            logger.warning(f"WebSearchProvider DDG search failed on '{query}': {exc}")

        # If DuckDuckGo returned 0 results (e.g. rate-limit/challenge), query Bing live search
        if not results:
            logger.info(f"Querying Bing live web discovery for '{query}'...")
            bing_results = await self._search_bing(query, limit=limit)
            if bing_results:
                results.extend(bing_results)

        return results[:limit]

    async def _search_bing(self, query: str, limit: int = 10) -> List[RawSearchResult]:
        import base64
        import urllib.parse

        results: List[RawSearchResult] = []
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            async with httpx.AsyncClient(timeout=8.0, headers=self._headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for item in soup.select("li.b_algo")[:limit]:
                        a_tag = item.select_one("h2 a")
                        if not a_tag or not a_tag.get("href"):
                            continue
                        title = a_tag.get_text(strip=True)
                        raw_href = a_tag["href"]
                        clean_href = raw_href

                        # If Bing redirect URL with u= parameter, decode the actual destination URL
                        if "/ck/a?!" in raw_href and "u=" in raw_href:
                            try:
                                qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                                if "u" in qs:
                                    u_val = qs["u"][0]
                                    b64_str = u_val[2:] if len(u_val) > 2 else u_val
                                    padded = b64_str + "=" * (-len(b64_str) % 4)
                                    decoded_url = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                                    if decoded_url.startswith("http"):
                                        clean_href = decoded_url
                            except Exception:
                                pass

                        snippet_el = item.select_one(".b_caption p") or item.select_one(".b_snippet")
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

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
                        elif "myntra" in domain:
                            source = "Myntra"
                        elif "ajio" in domain:
                            source = "Ajio"
                        elif "mi.com" in domain:
                            source = "Mi.com"

                        results.append(
                            RawSearchResult(
                                title=title,
                                snippet=snippet,
                                url=clean_href,
                                source=source,
                                domain=domain,
                            )
                        )

            logger.info(f"WebSearchProvider (Bing) returned {len(results)} results for '{query}'.")
        except Exception as exc:
            logger.warning(f"Bing search scraper failed on '{query}': {exc}")

        return results
