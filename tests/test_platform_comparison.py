from unittest.mock import patch
from backend.agent.platform_comparison import build_global_comparison
from backend.schemas.product import Product, ProductOffer, SearchResponse, PriceComparisonSummary
from backend.schemas.query import ShoppingRequirements
from tests.test_api_endpoints import mock_pipeline_products


def _search_response(products):
    return SearchResponse(
        query="Redmi Note 10S",
        requirements=ShoppingRequirements(raw_query="Redmi Note 10S", brand="Redmi", model="Note 10S"),
        products=products,
        alternatives=[],
        total_results=len(products),
        verified_results=len(products),
        sources=["Google Search Grounding"],
        data_source="live",
        search_status="success",
        comparison_summary=PriceComparisonSummary(
            product_name="Redmi Note 10S",
            lowest_price=14999.0,
            highest_price=15299.0,
            price_spread=300.0,
            best_price_platform="Amazon",
            offers_compared=2,
            recommendation="Amazon is lowest",
        ),
        timestamp="2026-10-05T12:00:00Z",
    )


def test_build_global_comparison_sorts_by_price_and_does_not_invent_mrp():
    payload = build_global_comparison(_search_response(mock_pipeline_products()))
    assert payload.query == "Redmi Note 10S"
    assert payload.total_sources_found == 2
    assert payload.comparison_results[0].platform == "Amazon"
    assert payload.comparison_results[0].price == 14999.0
    assert payload.comparison_results[0].direct_buy_url == "https://amazon.in/dp/B091J3M"
    assert payload.comparison_results[0].original_price is None
    assert payload.comparison_results[0].discount_percentage is None
    assert payload.best_deal_summary.recommended_platform == "Amazon"
    assert payload.best_deal_summary.lowest_price == 14999.0
    assert payload.best_deal_summary.savings_vs_highest == 300.0


def test_discount_computed_only_from_real_original_price():
    products = mock_pipeline_products()
    products[0].offers[0].original_price = 17999.0
    payload = build_global_comparison(_search_response(products))
    amazon = payload.comparison_results[0]
    assert amazon.original_price == 17999.0
    assert amazon.discount_percentage == "17%"


def test_compare_platforms_endpoint(client):
    with patch("backend.search.orchestrator.SearchOrchestrator.execute_search") as mock_exec:
        mock_exec.return_value = (mock_pipeline_products(), ["Google Search Grounding"], "live", False)
        res = client.get("/api/products/compare-platforms?query=Redmi+Note+10S")
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Redmi Note 10S"
        assert data["matched_product"]
        assert data["currency"] == "INR"
        assert data["total_sources_found"] >= 1
        assert isinstance(data["comparison_results"], list)
        first = data["comparison_results"][0]
        assert "platform" in first
        assert "direct_buy_url" in first
        assert first["direct_buy_url"].startswith("http")
        assert "recommended_platform" in data["best_deal_summary"]
        assert data["comparison_results"][0]["price"] <= data["comparison_results"][-1]["price"]


def test_query_generator_includes_site_operators():
    from backend.agent.query_generator import QueryGenerator
    from backend.agent.query_understander import QueryUnderstander

    req = QueryUnderstander()._extract_deterministic("Redmi Note 10S", False)
    queries = QueryGenerator.generate_focused_queries(req)
    assert any("site:amazon" in q and "site:flipkart.com" in q for q in queries)
