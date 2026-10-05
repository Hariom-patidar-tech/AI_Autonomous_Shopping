import pytest
from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import Product, ProductOffer, SearchResponse
from backend.search.product_page_verifier import ProductPageVerifier
from backend.agent.platform_comparison import build_global_comparison
from backend.agent.deduplicator import Deduplicator
from backend.agent.comparison_engine import ComparisonEngine
from backend.search.base import RawSearchResult
from backend.search.orchestrator import SearchOrchestrator


def test_variant_aware_deduplication():
    """Section 30: Do NOT merge 64GB with 128GB!"""
    p1 = Product(
        product_name="Redmi Note 10S (64GB Storage)",
        brand="Redmi",
        price=14999.0,
        url="https://amazon.in/dp/B01",
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
    )
    p2 = Product(
        product_name="Redmi Note 10S (128GB Storage)",
        brand="Redmi",
        price=16499.0,
        url="https://amazon.in/dp/B02",
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
    )
    p3_dup = Product(
        product_name="Redmi Note 10S (64GB Storage)",
        brand="Redmi",
        price=15299.0,
        url="https://flipkart.com/p/B01",
        source="Flipkart",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
        offers=[
            ProductOffer(
                platform="Flipkart",
                price=15299.0,
                url="https://flipkart.com/p/B01",
                observed_at="2026-10-05T12:00:00Z",
            )
        ]
    )

    deduped = Deduplicator.deduplicate([p1, p2, p3_dup])

    # Should keep both 64GB and 128GB as distinct products!
    assert len(deduped) == 2
    names = [p.product_name for p in deduped]
    assert "Redmi Note 10S (64GB Storage)" in names
    assert "Redmi Note 10S (128GB Storage)" in names

    # The 64GB product should now have offers from Flipkart merged!
    p_64 = next(p for p in deduped if "64GB" in p.product_name)
    assert any(o.platform == "Flipkart" for o in p_64.offers)


def test_matching_model_titles_merge_offers_without_merging_variants():
    products = [
        Product(
            product_name="Sony WF-C700N True Wireless Noise Cancelling Earbuds, Black",
            brand="Sony",
            model="WF-C700N",
            price=5999,
            currency="INR",
            url="https://www.amazon.in/dp/B0ABCDE123",
            source="Amazon",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
            offers=[ProductOffer(platform="Amazon", price=5999, currency="INR", url="https://www.amazon.in/dp/B0ABCDE123", observed_at="now")],
        ),
        Product(
            product_name="Sony WF-C700N Bluetooth Earphones, Black",
            brand="Sony",
            model="WF-C700N",
            price=6199,
            currency="INR",
            url="https://www.flipkart.com/p/sony-wf-c700n",
            source="Flipkart",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
            offers=[ProductOffer(platform="Flipkart", price=6199, currency="INR", url="https://www.flipkart.com/p/sony-wf-c700n", observed_at="now")],
        ),
        Product(
            product_name="Sony WF-C710N Earbuds",
            brand="Sony",
            model="WF-C710N",
            price=6999,
            currency="INR",
            url="https://www.amazon.in/dp/B0ABCDE456",
            source="Amazon",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
        ),
    ]

    deduplicated = Deduplicator.deduplicate(products)

    assert len(deduplicated) == 2
    matching_model = next(product for product in deduplicated if product.model == "WF-C700N")
    assert {offer.platform for offer in matching_model.offers} == {"Amazon", "Flipkart"}


def test_price_comparison_metrics():
    """Sections 26 & 27: calculate lowest_price, highest_price, price_spread, best_price_platform."""
    req = ShoppingRequirements(
        raw_query="iPhone 17 Pro",
        intent="cheapest_search",
    )

    offers = [
        ProductOffer(platform="Amazon", price=129999.0, url="https://amazon.in/dp/iph", observed_at="2026-10-05T12:00:00Z"),
        ProductOffer(platform="Flipkart", price=131499.0, url="https://flipkart.com/iph", observed_at="2026-10-05T12:00:00Z"),
        ProductOffer(platform="Croma", price=130990.0, url="https://croma.com/iph", observed_at="2026-10-05T12:00:00Z"),
    ]

    product = Product(
        product_name="iPhone 17 Pro",
        brand="Apple",
        price=129999.0,
        url="https://amazon.in/dp/iph",
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
        offers=offers,
    )

    summary = ComparisonEngine.generate_comparison_summary([product], req)

    assert summary is not None
    assert summary.lowest_price == 129999.0
    assert summary.highest_price == 131499.0
    assert summary.price_spread == 1500.0
    assert summary.best_price_platform == "Amazon"
    assert "Lowest verified price is ₹129,999.00 on Amazon" in summary.recommendation


def test_comparisons_do_not_compare_prices_across_currencies():
    usd_product = Product(
        product_name="Sony Headphones",
        brand="Sony",
        model="WH-1000XM5",
        price=300,
        currency="USD",
        url="https://www.amazon.com/dp/B0ABCDE123",
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
        offers=[
            ProductOffer(platform="Amazon", price=300, currency="USD", url="https://www.amazon.com/dp/B0ABCDE123", observed_at="now"),
            ProductOffer(platform="Best Buy", price=320, currency="USD", url="https://www.bestbuy.com/site/headphones/123.p", observed_at="now"),
            ProductOffer(platform="Flipkart", price=25000, currency="INR", url="https://www.flipkart.com/p/headphones", observed_at="now"),
        ],
    )
    req = ShoppingRequirements(raw_query="Sony WH-1000XM5", currency="USD")

    summary = ComparisonEngine.generate_comparison_summary([usd_product], req)
    search_response = SearchResponse(
        query=req.raw_query,
        requirements=req,
        products=[usd_product],
        total_results=1,
        verified_results=1,
        sources=["live"],
        timestamp="2026-10-05T12:00:00Z",
    )
    comparison = build_global_comparison(search_response)

    assert summary.currency == "USD"
    assert summary.lowest_price == 300
    assert summary.highest_price == 320
    assert comparison.currency == "USD"
    assert comparison.best_deal_summary.lowest_price == 300
    assert {item.currency for item in comparison.comparison_results} == {"USD", "INR"}


@pytest.mark.asyncio
async def test_search_orchestrator_continues_until_enough_verified_offers(monkeypatch):
    class StubProvider:
        def __init__(self, responses):
            self.responses = responses
            self.queries = []

        @property
        def name(self):
            return "stub"

        async def is_available(self):
            return True

        async def search(self, query, limit=10, additional_queries=None):
            self.queries.append(query)
            return self.responses.get(query, [])

    def raw_result(index):
        return RawSearchResult(
            title="Buy boAt Airdopes 141 earbuds",
            snippet="Retail product page",
            url=f"https://amazon.in/dp/B0ABCDE{index:03d}",
            source="Amazon",
        )

    primary = StubProvider({"earbuds": []})
    secondary = StubProvider({
        "first retailer query": [raw_result(1), raw_result(2)],
        "second retailer query": [raw_result(3), raw_result(4)],
        "third retailer query": [raw_result(5)],
    })

    async def verify_result(raw, client):
        if raw.url.endswith("002"):
            return None
        return Product(
            product_name="boAt Airdopes 141 TWS Earbuds",
            brand="boAt",
            model="Airdopes 141",
            price=899.0,
            currency="INR",
            url=raw.url,
            source=raw.source,
            image_url="https://m.media-amazon.com/images/I/earbuds.jpg",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
        )

    monkeypatch.setattr(ProductPageVerifier, "verify", staticmethod(verify_result))
    orchestrator = SearchOrchestrator(primary_provider=primary, secondary_provider=secondary)

    products, sources, _, _ = await orchestrator.execute_search(
        "earbuds",
        ["first retailer query", "second retailer query", "third retailer query"],
        ShoppingRequirements(raw_query="earbuds", category="headphones", keywords=["earbuds"]),
        limit=5,
    )

    assert len(products) == 4
    assert secondary.queries == [
        "earbuds",
        "first retailer query",
        "second retailer query",
        "third retailer query",
    ]
    assert "Web Search Provider" in sources
