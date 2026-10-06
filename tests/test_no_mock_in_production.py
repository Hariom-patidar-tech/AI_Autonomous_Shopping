import pytest
import importlib
from unittest.mock import patch
from backend.agent.shopping_pipeline import ShoppingPipeline
from backend.schemas.query import ShoppingRequirements


def test_no_fallback_catalog_module_in_backend():
    """Verify that backend.search.fallback_catalog does NOT exist and cannot be imported."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.search.fallback_catalog")


@pytest.mark.asyncio
async def test_provider_failure_returns_honest_error_not_mock():
    """Section 31 & Section 35: When live search provider fails, return provider_error, NEVER mock products."""
    pipeline = ShoppingPipeline()

    # Simulate provider failure (e.g. 429 quota exhaustion or network timeout)
    with patch.object(pipeline.orchestrator, "execute_search") as mock_exec:
        mock_exec.return_value = ([], [], "live", True)  # (products, sources, data_source, provider_error=True)

        res = await pipeline.run(query="iPhone 17 Pro")

        assert res.data_source == "live"
        assert res.search_status == "provider_error"
        assert "unavailable" in res.message.lower() or "quota" in res.message.lower()
        assert len(res.products) == 0
        assert len(res.alternatives) == 0


@pytest.mark.asyncio
async def test_zero_results_returns_no_verified_results_not_mock():
    """Section 30: When no real products are found, return no_verified_results, NEVER mock products."""
    pipeline = ShoppingPipeline()

    # Simulate live search returning 0 candidates without provider error
    with patch.object(pipeline.orchestrator, "execute_search") as mock_exec:
        mock_exec.return_value = ([], ["Google Search Grounding"], "live", False)

        res = await pipeline.run(query="obscure spare part 992817x")

        assert res.data_source == "live"
        assert res.search_status == "no_verified_results"
        assert "no products found" in res.message.lower() or "no verified" in res.message.lower()
        assert len(res.products) == 0
        assert len(res.alternatives) == 0


def test_api_search_failure_returns_provider_error(client):
    """API test: When provider fails, response returns 200 with provider_error status and empty products."""
    with patch("backend.search.orchestrator.SearchOrchestrator.execute_search") as mock_exec:
        mock_exec.return_value = ([], [], "live", True)

        res = client.get("/api/products/search?query=Redmi+Note+10S")
        assert res.status_code == 200
        data = res.json()
        assert data["data_source"] == "live"
        assert data["search_status"] == "provider_error"
        assert data["products"] == []
        assert data["alternatives"] == []
        assert "unavailable" in data["message"].lower() or "quota" in data["message"].lower()


def test_review_analyzer_no_hallucination_when_no_reviews():
    """Section 13: When no customer reviews exist, analyzer states no verified reviews, never invents fake themes."""
    from backend.agent.review_analyzer import ReviewAnalyzer
    analyzer = ReviewAnalyzer()

    # Run deterministic summary without evidence
    summary = analyzer._generate_deterministic_summary(
        product_name="Custom Artisanal Wooden Spoon",
        evidence=[],
        product_id=1,
        timestamp="2026-10-05T12:00:00Z"
    )

    assert summary.reviews_analyzed_count == 0
    assert summary.sentiment_score is None
    assert summary.positive_themes == []
    assert summary.negative_themes == []
    assert "No verified" in summary.overall_sentiment


def test_production_codebase_has_no_mock_catalog_variables():
    """Section 36: Verify that backend production modules have no MOCK_PRODUCTS or dummy catalogs."""
    import re
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    forbidden_patterns = [
        re.compile(r"^\s*(?:MOCK|DUMMY|SAMPLE|STATIC)_PRODUCTS\s*=", re.IGNORECASE),
        re.compile(r"^\s*mock_products\s*=", re.IGNORECASE),
        re.compile(r"^\s*sample_products\s*=", re.IGNORECASE),
        re.compile(r"^\s*fallback_products\s*=", re.IGNORECASE),
    ]

    violating_lines = []
    for py_file in backend_dir.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, 1):
            for pat in forbidden_patterns:
                if pat.search(line):
                    violating_lines.append(f"{py_file.name}:{idx} -> {line.strip()}")

    assert not violating_lines, f"Found mock product definitions in backend: {violating_lines}"

