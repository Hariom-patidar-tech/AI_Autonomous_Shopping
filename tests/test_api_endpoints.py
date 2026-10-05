import pytest
from unittest.mock import patch
from backend.schemas.product import Product, ProductOffer


def mock_pipeline_products():
    return [
        Product(
            id=1,
            product_name="Redmi Note 10S (Frost White, 64 GB)",
            brand="Redmi",
            model="Note 10S",
            price=14999.0,
            currency="INR",
            rating=4.3,
            review_count=18200,
            seller="Amazon Retail",
            availability=True,
            delivery="Free delivery by tomorrow",
            url="https://amazon.in/dp/B091J3M",
            source="Amazon",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
            offers=[
                ProductOffer(
                    platform="Amazon",
                    price=14999.0,
                    url="https://amazon.in/dp/B091J3M",
                    observed_at="2026-10-05T12:00:00Z",
                ),
                ProductOffer(
                    platform="Flipkart",
                    price=15299.0,
                    url="https://flipkart.com/redmi-note-10s",
                    observed_at="2026-10-05T12:00:00Z",
                ),
            ],
        )
    ]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_search_get_endpoint(client):
    with patch("backend.search.orchestrator.SearchOrchestrator.execute_search") as mock_exec:
        mock_exec.return_value = (mock_pipeline_products(), ["Google Search Grounding"], "live", False)
        res = client.get("/api/products/search?query=Redmi+Note+10S")

        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Redmi Note 10S"
        assert len(data["products"]) >= 1
        p = data["products"][0]
        assert "Redmi Note 10S" in p["product_name"]
        assert len(p["offers"]) == 2
        assert data["data_source"] == "live"


def test_search_post_endpoint(client):
    with patch("backend.search.orchestrator.SearchOrchestrator.execute_search") as mock_exec:
        mock_exec.return_value = (mock_pipeline_products(), ["Google Search Grounding"], "live", False)
        res = client.post("/api/products/search", json={"query": "Redmi Note 10S", "budget_max": 20000})

        assert res.status_code == 200
        data = res.json()
        assert data["search_status"] == "success"


def test_cart_add_endpoint(client):
    res = client.post(
        "/api/cart/add",
        json={
            "product_name": "Redmi Note 10S",
            "platform": "Amazon",
            "product_url": "https://amazon.in/dp/B091J3M",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "manual_action_required"
    assert data["mode"] == "manual_handoff"


def test_checkout_approve_endpoint(client):
    res = client.post(
        "/api/cart/checkout/approve",
        json={
            "product_name": "Redmi Note 10S",
            "platform": "Amazon",
            "product_url": "https://amazon.in/dp/B091J3M",
            "total_amount": 14999.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready_for_human_approval"
    assert data["requires_human_approval"] is True


def test_review_analyze_endpoint(client):
    res = client.post(
        "/api/reviews/analyze",
        json={"product_name": "Redmi Note 10S"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "overall_sentiment" in data
    assert "positive_themes" in data
    assert "common_defects" in data


def test_history_endpoint(client):
    res = client.get("/api/history?user_id=1")
    assert res.status_code == 200
    data = res.json()
    assert "searches" in data


def test_comparison_endpoint_error_handling(client):
    res = client.post("/api/comparison", json={"product_ids": [99999]})
    assert res.status_code == 404
