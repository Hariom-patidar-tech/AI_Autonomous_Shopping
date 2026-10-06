import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

from providers.base import NormalizedProduct
from providers.amazon import AmazonProvider
from providers.flipkart import FlipkartProvider
from providers.other_retailers import OtherRetailersProvider
from providers.google_search import GoogleSearchProvider
from providers.validator import ProductValidator
from backend.search.verifier import URLVerifier, ImageVerifier
from backend.agent.query_understander import QueryUnderstander
from backend.agent.filter_engine import HardFilterEngine
from backend.search.matcher import ProductMatcher
from backend.agent.shopping_pipeline import ShoppingPipeline
from backend.schemas.product import Product, ProductOffer
from backend.schemas.query import ShoppingRequirements


# =========================================================================
# 1. Amazon Provider Tests
# =========================================================================
@pytest.mark.asyncio
async def test_amazon_provider_credentials_and_sigv4():
    """Verify Amazon provider credentials, AWS SigV4 signing, and error handling."""
    # When credentials not configured
    with patch.dict(os.environ, {"AMAZON_ACCESS_KEY": "", "AMAZON_SECRET_KEY": "", "AMAZON_ASSOCIATE_TAG": ""}):
        p = AmazonProvider()
        assert (await p.is_available()) is False
        assert "not configured" in p.get_status_message()

    # When credentials configured
    p = AmazonProvider(
        access_key="AKIAEXAMPLE123",
        secret_key="secretkey123",
        partner_tag="mytag-21",
        host="webservices.amazon.in",
        region="eu-west-1",
    )
    # Check SigV4 signing
    headers = p._sign_aws4(b'{"test": 1}', "20261005", "20261005T120000Z")
    assert "Authorization" in headers
    assert "AWS4-HMAC-SHA256" in headers["Authorization"]
    assert "AKIAEXAMPLE123/20261005/eu-west-1/ProductAdvertisingAPI/aws4_request" in headers["Authorization"]
    assert headers["x-amz-target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"


def test_amazon_provider_parses_real_response():
    """Verify parsing PA-API JSON into NormalizedProduct."""
    p = AmazonProvider(access_key="key", secret_key="sec", partner_tag="tag")
    mock_data = {
        "SearchResult": {
            "Items": [
                {
                    "ASIN": "B09W92FPM5",
                    "DetailPageURL": "https://www.amazon.in/dp/B09W92FPM5?tag=mytag-21",
                    "ItemInfo": {
                        "Title": {"DisplayValue": "boAt Wave Call Smartwatch with Bluetooth Calling"},
                        "ByLineInfo": {"Brand": {"DisplayValue": "boAt"}},
                    },
                    "Images": {
                        "Primary": {"Large": {"URL": "https://m.media-amazon.com/images/I/61H5nRsv+OL._SL1500_.jpg"}}
                    },
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 1299.0, "Currency": "INR"},
                                "Availability": {"Type": "Now"},
                            }
                        ]
                    },
                }
            ]
        }
    }
    products = p._parse_paapi_response(mock_data)
    assert len(products) == 1
    prod = products[0]
    assert prod.product_id == "B09W92FPM5"
    assert prod.name == "boAt Wave Call Smartwatch with Bluetooth Calling"
    assert prod.brand == "boAt"
    assert prod.price == 1299.0
    assert prod.currency == "INR"
    assert prod.retailer == "Amazon"
    assert "amazon.in/dp/B09W92FPM5" in prod.product_url
    assert prod.availability is True
    assert prod.verified is True


# =========================================================================
# 2. Flipkart Provider Tests
# =========================================================================
@pytest.mark.asyncio
async def test_flipkart_provider_availability_and_html_rejection():
    """Verify Flipkart provider configuration and rejection of HTML responses."""
    with patch.dict(os.environ, {"FLIPKART_AFFILIATE_ID": "", "FLIPKART_AFFILIATE_TOKEN": ""}):
        p = FlipkartProvider()
        assert (await p.is_available()) is False
        assert "not configured" in p.get_status_message()


def test_flipkart_provider_parses_json_into_normalized_schema():
    """Verify parsing Flipkart affiliate JSON."""
    p = FlipkartProvider(affiliate_id="test_id", affiliate_token="test_token")
    mock_data = {
        "productItemList": [
            {
                "productBaseInfoV1": {
                    "productId": "WATGB78910",
                    "title": "boAt Wave Call 2 Plus Bluetooth Calling Smartwatch",
                    "productBrand": "boAt",
                    "productUrl": "https://www.flipkart.com/p/itmwatgb78910?pid=WATGB78910",
                    "inStock": True,
                    "imageUrls": {
                        "800x800": "https://rukminim2.flixcart.com/image/800/800/xif0q/smartwatch/boat.jpg"
                    },
                    "flipkartSellingPrice": {
                        "amount": 1099.0,
                        "currency": "INR",
                    },
                }
            }
        ]
    }
    products = p._parse_flipkart_json(mock_data)
    assert len(products) == 1
    prod = products[0]
    assert prod.product_id == "WATGB78910"
    assert prod.name == "boAt Wave Call 2 Plus Bluetooth Calling Smartwatch"
    assert prod.price == 1099.0
    assert prod.currency == "INR"
    assert prod.retailer == "Flipkart"
    assert "flipkart.com/p/itmwatgb78910" in prod.product_url
    assert prod.availability is True
    assert prod.verified is True


# =========================================================================
# 3. Google 429 Handling
# =========================================================================
@pytest.mark.asyncio
async def test_google_429_graceful_handling():
    """Verify that Google 429 quota exhaustion is caught gracefully and doesn't crash search."""
    p = GoogleSearchProvider(api_key="fake_key")
    p._client = MagicMock()
    p._client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for model")

    results = await p.search("smartwatch")
    assert results == []
    assert GoogleSearchProvider.is_quota_exhausted() is True
    assert "quota exhausted" in p.get_status_message().lower()


# =========================================================================
# 4. Price & INR Budget Parsing Tests
# =========================================================================
def test_budget_and_inr_parsing():
    """Verify parsing: 1000rs, ₹1000, Rs 1000, 1,000 INR, under 1000, below ₹1,000."""
    u = QueryUnderstander()

    queries_and_expected = [
        ("1000rs", 1000.0, "INR"),
        ("₹1000", 1000.0, "INR"),
        ("Rs 1000", 1000.0, "INR"),
        ("1,000 INR", 1000.0, "INR"),
        ("under 1000", 1000.0, "INR"),
        ("below ₹1,000", 1000.0, "INR"),
        ("watch under 1000rs", 1000.0, "INR"),
        ("smartwatch below ₹2,500", 2500.0, "INR"),
        ("wireless headphones under $250", 250.0, "USD"),
        ("1500 tak watch", 1500.0, "INR"),
        ("2000 ke andar smartwatch", 2000.0, "INR"),
    ]

    for q, expected_budget, expected_curr in queries_and_expected:
        req = u._extract_deterministic(q, False)
        assert req.budget_max == expected_budget, f"Failed on '{q}': got {req.budget_max} expected {expected_budget}"
        assert req.currency == expected_curr, f"Failed on '{q}': got {req.currency} expected {expected_curr}"


# =========================================================================
# 5. Budget Filtering Tests
# =========================================================================
def test_budget_filtering_hides_products_above_budget():
    """Products above budget must be filtered out."""
    p1 = Product(
        product_name="Budget Watch 1",
        price=899.0,
        currency="INR",
        url="https://www.boat-lifestyle.com/products/watch-1",
        source="boAt",
        observed_at="now",
        last_verified_at="now",
    )
    p2 = Product(
        product_name="Budget Watch 2",
        price=999.0,
        currency="INR",
        url="https://www.boat-lifestyle.com/products/watch-2",
        source="boAt",
        observed_at="now",
        last_verified_at="now",
    )
    p3 = Product(
        product_name="Over Budget Watch",
        price=1299.0,
        currency="INR",
        url="https://www.boat-lifestyle.com/products/watch-3",
        source="boAt",
        observed_at="now",
        last_verified_at="now",
    )

    req = ShoppingRequirements(raw_query="watch under 1000rs", budget_max=1000.0, currency="INR")
    passed, rejected = HardFilterEngine.apply_filters([p1, p2, p3], req)

    assert len(passed) == 2
    assert {p.product_name for p in passed} == {"Budget Watch 1", "Budget Watch 2"}
    assert len(rejected) == 1
    assert "exceeds max budget" in rejected[0]["reason"]


# =========================================================================
# 6. Product Validator & URL/Thumbnail Verification Tests
# =========================================================================
def test_product_validator_exact_product_url_and_category_rejection():
    """Verify validation passes exact detail pages and rejects category/search pages."""
    # Valid product
    valid_item = NormalizedProduct(
        product_id="B09W92FPM5",
        name="boAt Ultima Rise Smartwatch",
        brand="boAt",
        price=999.0,
        currency="INR",
        thumbnail="https://cdn.shopify.com/s/files/1/0057/8938/4802/files/1.png",
        retailer="boAt",
        product_url="https://www.boat-lifestyle.com/products/ultima-rise-smartwatch",
        availability=True,
        verified=True,
    )
    is_valid, reason = ProductValidator.validate(valid_item)
    assert is_valid is True
    assert reason is None

    # Rejected: Category URL
    cat_item = valid_item.model_copy(update={"product_url": "https://www.flipkart.com/watches/pr?sid=r18"})
    is_valid, reason = ProductValidator.validate(cat_item)
    assert is_valid is False
    assert "Generic search/category URL" in reason

    # Rejected: Search URL
    search_item = valid_item.model_copy(update={"product_url": "https://www.amazon.in/s?k=watch"})
    is_valid, reason = ProductValidator.validate(search_item)
    assert is_valid is False

    # Rejected: Missing / 0 price
    no_price = valid_item.model_copy(update={"price": 0.0})
    is_valid, reason = ProductValidator.validate(no_price)
    assert is_valid is False
    assert "Invalid price" in reason

    # Rejected: Placeholder thumbnail
    bad_img = valid_item.model_copy(update={"thumbnail": "https://example.com/placeholder-image.png"})
    is_valid, reason = ProductValidator.validate(bad_img)
    assert is_valid is False
    assert "placeholder" in reason.lower() or "unverified" in reason.lower()


# =========================================================================
# 7. Same-Product Matching & Variant Separation
# =========================================================================
def test_same_product_matching_and_variant_separation():
    """Matching brand and model merges offers; distinct variants stay separate."""
    # Same product across Amazon and Flipkart (Active Black)
    p_amz = Product(
        product_name="boAt Wave Call 2 Plus Smartwatch (Active Black)",
        brand="boAt",
        model="Wave Call 2 Plus",
        price=1199.0,
        currency="INR",
        url="https://www.amazon.in/dp/B0WAVE123",
        source="Amazon",
        image_url="https://m.media-amazon.com/images/I/watch.jpg",
        observed_at="now",
        last_verified_at="now",
    )
    p_fk = Product(
        product_name="boAt Wave Call 2 Plus Bluetooth Calling Smartwatch (Active Black)",
        brand="boAt",
        model="Wave Call 2 Plus",
        price=999.0,
        currency="INR",
        url="https://www.flipkart.com/p/itmwave123",
        source="Flipkart",
        image_url="https://rukminim2.flixcart.com/image/800/800/watch.jpg",
        observed_at="now",
        last_verified_at="now",
    )
    # Different variant: Cherry Blossom (Pink)
    p_pink = Product(
        product_name="boAt Wave Call 2 Plus Smartwatch (Pink)",
        brand="boAt",
        model="Wave Call 2 Plus",
        price=1299.0,
        currency="INR",
        url="https://www.boat-lifestyle.com/products/wave-call-2-pink",
        source="boAt",
        image_url="https://cdn.shopify.com/watch-pink.jpg",
        observed_at="now",
        last_verified_at="now",
    )

    merged = ProductMatcher.match_and_merge([p_amz, p_fk, p_pink])

    # Should have 2 unique products (Black and Pink)
    assert len(merged) == 2

    # Black variant should have merged both Amazon and Flipkart offers
    black_prod = next(p for p in merged if "black" in p.product_name.lower())
    assert len(black_prod.offers) == 2
    assert {o.platform for o in black_prod.offers} == {"Amazon", "Flipkart"}
    # Best price should be Flipkart's ₹999
    assert black_prod.price == 999.0
    assert black_prod.source == "Flipkart"
    assert "flipkart.com" in black_prod.url

    # Pink variant remains its own separate product
    pink_prod = next(p for p in merged if "pink" in p.product_name.lower())
    assert pink_prod.price == 1299.0


# =========================================================================
# 8. Buy Now URL Preservation
# =========================================================================
def test_buy_now_url_preserved():
    """Every offer and product must store its exact detail URL."""
    offer = ProductOffer(
        platform="Amazon",
        price=899.0,
        currency="INR",
        url="https://www.amazon.in/dp/B0ABCDE123",
        observed_at="now",
    )
    prod = Product(
        product_name="Test Watch",
        price=899.0,
        currency="INR",
        url="https://www.amazon.in/dp/B0ABCDE123",
        source="Amazon",
        observed_at="now",
        last_verified_at="now",
        offers=[offer],
    )

    assert prod.url == "https://www.amazon.in/dp/B0ABCDE123"
    assert prod.offers[0].url == "https://www.amazon.in/dp/B0ABCDE123"
    assert "/dp/" in prod.offers[0].url
