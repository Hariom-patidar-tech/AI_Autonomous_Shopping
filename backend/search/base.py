from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel


class RawSearchResult(BaseModel):
    title: str
    snippet: str
    url: str
    source: str
    price_text: Optional[str] = None
    image_url: Optional[str] = None
    domain: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.domain and self.url:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc.lower().replace("www.", "")
            except Exception:
                self.domain = ""


class SearchCandidate(BaseModel):
    raw_title: str
    raw_snippet: str
    url: str
    source: str
    domain: str
    estimated_price: Optional[float] = None
    image_url: Optional[str] = None
    is_product_page: bool = True
    relevance_hint: float = 1.0


class SearchProvider(ABC):
    """Abstract base class for all search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider credentials/network are active."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[RawSearchResult]:
        """Execute a web search for the query and return raw search results."""
        pass
