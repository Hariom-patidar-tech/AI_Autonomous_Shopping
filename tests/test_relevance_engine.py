import pytest
from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import Product
from backend.agent.relevance_engine import RelevanceEngine


def create_product(name: str, brand: str = "Brand", price: float = 10000.0, url: str = "https://amazon.in/dp/B01"):
    return Product(
        product_name=name,
        brand=brand,
        price=price,
        currency="INR",
        url=url,
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
    )


def test_category_mismatch_protection_clothing_vs_electronics():
    """Test E & Section 15: 'cat logo t-shirt' MUST reject TVs, phones, laptops."""
    req = ShoppingRequirements(
        raw_query="cat logo t-shirt",
        category="clothing",
        product_type="t-shirt",
        keywords=["cat", "logo", "t-shirt"],
    )

    products = [
        create_product("Cat Print Cotton Graphic T-Shirt", "Bewakoof"),
        create_product("Sony Bravia 55 inch 4K Ultra HD Smart TV", "Sony"),
        create_product("Redmi Note 10S 6GB 64GB Smartphone", "Redmi"),
        create_product("HP Pavilion Gaming Laptop 16GB RAM", "HP"),
    ]

    exact, alternatives = RelevanceEngine.evaluate(products, req)
    all_retained = exact + alternatives

    # TVs, phones, and laptops must be rejected!
    retained_names = [p.product_name for p in all_retained]
    assert "Cat Print Cotton Graphic T-Shirt" in retained_names
    assert "Sony Bravia 55 inch 4K Ultra HD Smart TV" not in retained_names
    assert "Redmi Note 10S 6GB 64GB Smartphone" not in retained_names
    assert "HP Pavilion Gaming Laptop 16GB RAM" not in retained_names


def test_exact_model_vs_alternative():
    """Test B & Section 16: Redmi Note 10S exact match vs Redmi Note 11 (alternative) vs Samsung (rejected)."""
    req = ShoppingRequirements(
        raw_query="Redmi Note 10S",
        category="smartphone",
        brand="Redmi",
        model="Note 10S",
        intent="exact_product_search",
    )

    products = [
        create_product("Redmi Note 10S 6GB RAM 64GB Storage", "Redmi"),
        create_product("Redmi Note 10S 6GB RAM 128GB Storage", "Redmi"),
        create_product("Redmi Note 11 4GB RAM 64GB Storage", "Redmi"),
        create_product("Samsung Galaxy M14 5G", "Samsung"),
    ]

    exact, alternatives = RelevanceEngine.evaluate(products, req)

    exact_names = [p.product_name for p in exact]
    alt_names = [p.product_name for p in alternatives]

    assert "Redmi Note 10S 6GB RAM 64GB Storage" in exact_names
    assert "Redmi Note 10S 6GB RAM 128GB Storage" in exact_names
    assert "Redmi Note 11 4GB RAM 64GB Storage" in alt_names
    # Samsung is wrong brand for exact model search
    assert "Samsung Galaxy M14 5G" not in exact_names


def test_headphones_query_rejects_generic_store_pages():
    req = ShoppingRequirements(
        raw_query="earbuds under 1000rs",
        category="headphones",
        product_type="headphones",
        keywords=["earbuds"],
    )
    products = [
        create_product("Earbuds (Wired or Wireless)", brand=None),
        create_product("Amazon.in: Earbuds", brand=None),
        create_product("boAt Airdopes 141 TWS Earbuds", brand="boAt"),
    ]

    exact, alternatives = RelevanceEngine.evaluate(products, req)
    names = [product.product_name for product in exact + alternatives]

    assert names == ["boAt Airdopes 141 TWS Earbuds"]
