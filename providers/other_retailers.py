from __future__ import annotations
import asyncio
import logging
import re
from typing import List, Optional, Any, Dict
from urllib.parse import quote_plus, urljoin
import httpx

from providers.base import BaseProvider, NormalizedProduct

logger = logging.getLogger("shopping_agent.providers.other_retailers")

RETAILERS = [
    {
        "name": "boAt",
        "domain": "boat-lifestyle.com",
        "base_url": "https://www.boat-lifestyle.com",
        "brand": "boAt",
    },
    {
        "name": "Noise",
        "domain": "gonoise.com",
        "base_url": "https://www.gonoise.com",
        "brand": "Noise",
    },
    {
        "name": "Boult",
        "domain": "boultaudio.com",
        "base_url": "https://www.boultaudio.com",
        "brand": "Boult",
    },
    {
        "name": "Fire-Boltt",
        "domain": "fireboltt.com",
        "base_url": "https://www.fireboltt.com",
        "brand": "Fire-Boltt",
    },
]


class OtherRetailersProvider(BaseProvider):
    """
    Live Product Connector for direct brand retailers (boAt, Noise, Boult, Fire-Boltt).
    Extracts 100% REAL products, real selling prices, exact product URLs, and official CDN thumbnails.
    Zero mock, dummy, or fabricated items.
    """

    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self._headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        self.last_error: Optional[str] = None
        self._successful_stores: List[str] = []

    @property
    def name(self) -> str:
        return "OtherRetailers"

    async def is_available(self) -> bool:
        """Direct retailer endpoints are open and live."""
        return True

    def get_status_message(self) -> str:
        if self._successful_stores:
            return f"Connected to {', '.join(self._successful_stores)}"
        if self.last_error:
            return f"Other retailers error: {self.last_error}"
        return "Other retailers live"

    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Query direct brand stores concurrently and return verified normalized products."""
        clean_terms = self._extract_clean_search_terms(query)
        logger.info(f"OtherRetailersProvider searching for terms: '{clean_terms}' (original: '{query}')")

        budget_max = None
        if requirements and hasattr(requirements, "budget_max") and requirements.budget_max is not None:
            budget_max = float(requirements.budget_max)

        tasks = [
            self._search_store(store, clean_terms, limit=limit, budget_max=budget_max)
            for store in RETAILERS
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        aggregated: List[NormalizedProduct] = []
        self._successful_stores = []

        for store, res in zip(RETAILERS, results):
            if isinstance(res, Exception):
                logger.warning(f"Retailer '{store['name']}' query failed: {res}")
                continue
            if isinstance(res, list) and res:
                self._successful_stores.append(store["name"])
                aggregated.extend(res)

        logger.info(f"OtherRetailersProvider gathered {len(aggregated)} products from {len(self._successful_stores)} stores.")
        return aggregated

    async def _search_store(
        self,
        store: Dict[str, str],
        search_terms: str,
        limit: int = 10,
        budget_max: Optional[float] = None,
    ) -> List[NormalizedProduct]:
        """Search a single brand store using its search endpoint and product catalog."""
        store_products: List[NormalizedProduct] = []
        base_url = store["base_url"]
        brand = store["brand"]

        # 1. Search suggest endpoint
        suggest_url = f"{base_url}/search/suggest.json?q={quote_plus(search_terms)}&resources[type]=product"
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(suggest_url)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_prods = (
                        data.get("resources", {}).get("results", {}).get("products", [])
                        or data.get("products", [])
                    )
                    for item in raw_prods:
                        norm = self._normalize_item(item, base_url, brand, search_terms=search_terms)
                        if norm:
                            store_products.append(norm)

                # 2. If budget specified or few items returned, check store products catalog
                if len(store_products) < limit or budget_max is not None:
                    catalog_url = f"{base_url}/products.json?limit=250"
                    cat_resp = await client.get(catalog_url)
                    if cat_resp.status_code == 200:
                        cat_data = cat_resp.json()
                        cat_prods = cat_data.get("products", [])
                        terms_lower = [t for t in search_terms.lower().split() if len(t) > 2]
                        for item in cat_prods:
                            title = item.get("title", "")
                            p_type = item.get("product_type", "")
                            combined_text = f"{title} {p_type}".lower()
                            if all(term in combined_text for term in terms_lower):
                                norm = self._normalize_catalog_item(item, base_url, brand)
                                if norm and norm.product_url not in {p.product_url for p in store_products}:
                                    store_products.append(norm)

        except Exception as exc:
            logger.debug(f"Store search failed for {store['name']}: {exc}")

        if budget_max is not None:
            # Prioritize items within requested budget
            store_products.sort(key=lambda p: (0 if p.price <= budget_max else 1, p.price))

        return store_products[:limit]

    def _normalize_item(self, item: dict, base_url: str, brand: str, search_terms: str = "") -> Optional[NormalizedProduct]:
        """Convert suggest.json product object to NormalizedProduct."""
        try:
            title = item.get("title")
            if not title or len(title.strip()) < 3:
                return None

            if search_terms:
                terms_lower = [t for t in search_terms.lower().split() if len(t) > 2]
                title_lower = title.lower()
                if terms_lower and not any(t in title_lower for t in terms_lower):
                    return None

            raw_price = item.get("price")
            if raw_price is None:
                return None
            price = float(raw_price)
            if price <= 0:
                return None

            image_url = item.get("image") or item.get("featured_image")
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url
            if not image_url or not image_url.startswith("http"):
                return None

            raw_url = item.get("url") or ""
            handle = item.get("handle")
            if not raw_url and handle:
                raw_url = f"/products/{handle}"
            if not raw_url:
                return None

            product_url = urljoin(base_url, raw_url)
            # Ensure it is an exact product detail URL
            if not re.search(r"/products/[a-z0-9\-]+", product_url, re.I):
                return None

            item_id = str(item.get("id") or handle or product_url)
            available = item.get("available", True)

            # Model extraction
            model = None
            if "|" in title:
                parts = title.split("|", 1)
                model = parts[0].replace(brand, "").strip()

            return NormalizedProduct(
                product_id=item_id,
                name=title.strip(),
                brand=brand,
                model=model,
                variant=None,
                price=price,
                currency="INR",
                thumbnail=image_url,
                retailer=brand,
                product_url=product_url,
                availability=bool(available),
                verified=True,
            )
        except Exception:
            return None

    def _normalize_catalog_item(self, item: dict, base_url: str, brand: str) -> Optional[NormalizedProduct]:
        """Convert products.json catalog item to NormalizedProduct."""
        try:
            title = item.get("title")
            handle = item.get("handle")
            if not title or not handle:
                return None

            variants = item.get("variants", [])
            if not variants:
                return None

            # Get first active variant
            var = variants[0]
            price = float(var.get("price", 0))
            if price <= 0:
                return None

            images = item.get("images", [])
            image_url = images[0].get("src") if images else None
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url
            if not image_url or not image_url.startswith("http"):
                return None

            product_url = urljoin(base_url, f"/products/{handle}")
            available = var.get("available", True)

            model = None
            if "|" in title:
                parts = title.split("|", 1)
                model = parts[0].replace(brand, "").strip()

            return NormalizedProduct(
                product_id=str(item.get("id") or var.get("id")),
                name=title.strip(),
                brand=brand,
                model=model,
                variant=var.get("title") if var.get("title") != "Default Title" else None,
                price=price,
                currency="INR",
                thumbnail=image_url,
                retailer=brand,
                product_url=product_url,
                availability=bool(available),
                verified=True,
            )
        except Exception:
            return None

    def _extract_clean_search_terms(self, query: str) -> str:
        """Strip budget, stop-words, and filler phrases to extract pure product terms."""
        lower = query.lower()
        # Remove budget patterns like 'under 1000', '1000rs', 'below 5000', 'ke andar'
        clean = re.sub(
            r"(?:under|below|less\s+than|within|ke\s*andar|tak|me|mein)?\s*(?:₹|rs\.?|inr)?\s*[\d,]+\s*(?:k|lakh)?\s*(?:rs|inr|rupees?)?",
            "",
            lower,
        )
        # Remove non-alphanumeric words except hyphens
        clean = re.sub(r"[^\w\s\-]", " ", clean)
        stop_words = {
            "i", "want", "need", "show", "find", "me", "a", "for", "with", "good", "best",
            "price", "buy", "online", "chahiye", "kaha", "sasta", "milega", "the", "and",
        }
        tokens = [w for w in clean.split() if w not in stop_words and len(w) > 1]
        return " ".join(tokens) or query
