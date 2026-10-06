from backend.search.base import SearchProvider, RawSearchResult, SearchCandidate
from backend.search.google_provider import GoogleSearchProvider
from backend.search.web_provider import WebSearchProvider
from backend.search.verifier import URLVerifier, ImageVerifier
from backend.search.extractor import CandidateDetector, ProductPageExtractor

def __getattr__(name: str):
    if name == "SearchOrchestrator":
        from backend.search.orchestrator import SearchOrchestrator
        return SearchOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SearchProvider",
    "RawSearchResult",
    "SearchCandidate",
    "GoogleSearchProvider",
    "WebSearchProvider",
    "URLVerifier",
    "ImageVerifier",
    "CandidateDetector",
    "ProductPageExtractor",
    "SearchOrchestrator",
]
