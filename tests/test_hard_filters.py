import pytest
from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import Product
from backend.agent.filter_engine import HardFilterEngine


def make_product(name: str, price=None, rating=None, availability=True):
    return Product(
        product_name=name,
        price=price,
        rating=rating,
        availability=availability,
        url="https://amazon.in/dp/test",
        source="Amazon",
        observed_at="2026-10-05T12:00:00Z",
        last_verified_at="2026-10-05T12:00:00Z",
    )


def test_deterministic_budget_filter():
    """Section 17: under ₹50,000 means ₹50,001 MUST be rejected."""
    req = ShoppingRequirements(
        raw_query="laptop under 50000",
        budget_max=50000.0,
    )

    p_valid = make_product("Budget Laptop", price=49999.0)
    p_exact_border = make_product("Border Laptop", price=50000.0)
    p_rejected = make_product("Over Budget Laptop", price=50001.0)

    passed, rejections = HardFilterEngine.apply_filters([p_valid, p_exact_border, p_rejected], req)

    passed_names = [p.product_name for p in passed]
    assert "Budget Laptop" in passed_names
    assert "Border Laptop" in passed_names
    assert "Over Budget Laptop" not in passed_names
    assert any("50,001" in r["reason"] for r in rejections)


def test_budget_filter_rejects_unknown_price():
    req = ShoppingRequirements(raw_query="earbuds under 1000rs", budget_max=1000.0)
    product = make_product("boAt Airdopes 141 Earbuds", price=None)

    passed, rejections = HardFilterEngine.apply_filters([product], req)

    assert passed == []
    assert "cannot verify" in rejections[0]["reason"]


def test_deterministic_rating_filter():
    """Section 17: minimum rating 4.0 means 3.8 MUST be rejected."""
    req = ShoppingRequirements(
        raw_query="best headphones rating 4.0",
        min_rating=4.0,
    )

    p_good = make_product("Good Headphones", rating=4.2)
    p_low = make_product("Low Rated Headphones", rating=3.8)

    passed, rejections = HardFilterEngine.apply_filters([p_good, p_low], req)

    passed_names = [p.product_name for p in passed]
    assert "Good Headphones" in passed_names
    assert "Low Rated Headphones" not in passed_names


def test_out_of_stock_rejected():
    """Section 17: out of stock products excluded from purchasable results."""
    req = ShoppingRequirements(raw_query="smartphone")

    p_in_stock = make_product("Phone In Stock", availability=True)
    p_out = make_product("Phone Out of Stock", availability=False)

    passed, _ = HardFilterEngine.apply_filters([p_in_stock, p_out], req)
    passed_names = [p.product_name for p in passed]
    assert "Phone In Stock" in passed_names
    assert "Phone Out of Stock" not in passed_names


def test_unknown_data_preserves_none():
    """Section 18: Unknown data means unknown. None is never converted to 5 or 0."""
    p = make_product("Mystery Item", price=None, rating=None, availability=None)
    req = ShoppingRequirements(raw_query="item")

    passed, _ = HardFilterEngine.apply_filters([p], req)
    assert len(passed) == 1
    assert passed[0].price is None
    assert passed[0].rating is None
    assert passed[0].availability is None
