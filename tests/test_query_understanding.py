import pytest
from backend.agent.query_understander import QueryUnderstander
from backend.agent.query_generator import QueryGenerator


@pytest.mark.asyncio
async def test_natural_language_laptop_coding():
    """Test C: 'I need a laptop under ₹60000 for coding'"""
    understander = QueryUnderstander()
    req = await understander.understand("I need a laptop under ₹60000 for coding")

    assert req.category == "laptop"
    assert req.budget_max == 60000.0
    assert req.use_case == "coding"
    assert req.currency == "INR"


@pytest.mark.asyncio
async def test_hindi_hinglish_tv_query():
    """Test D: 'mujhe 50000 ke andar 55 inch 4k tv chahiye'"""
    understander = QueryUnderstander()
    req = await understander.understand("mujhe 50000 ke andar 55 inch 4k tv chahiye")

    assert req.category == "television"
    assert req.budget_max == 50000.0
    assert req.is_hindi_hinglish is True


@pytest.mark.asyncio
async def test_exact_model_redmi_note_10s():
    """Test B: 'Redmi Note 10S'"""
    understander = QueryUnderstander()
    req = await understander.understand("Redmi Note 10S")

    assert req.brand.lower() == "redmi"
    assert "10" in req.model
    assert req.intent in ("exact_product_search", "product_search")


@pytest.mark.asyncio
async def test_arbitrary_product_cat_tshirt():
    """Test E: 'cat logo t-shirt'"""
    understander = QueryUnderstander()
    req = await understander.understand("cat logo t-shirt")

    assert req.category == "clothing"
    assert "cat" in req.keywords
    assert "logo" in req.keywords


def test_query_generator_exact_model():
    """Verify focused queries generated for exact product."""
    understander = QueryUnderstander()
    req = understander._extract_deterministic("Redmi Note 10S", False)
    queries = QueryGenerator.generate_focused_queries(req)

    assert len(queries) >= 3
    assert any("Redmi" in q for q in queries)
    assert any("price" in q.lower() or "buy" in q.lower() for q in queries)


def test_earbuds_budget_with_attached_rupee_suffix():
    req = QueryUnderstander()._extract_deterministic("earbuds under 1000rs", False)

    assert req.category == "headphones"
    assert req.budget_max == 1000.0
    assert req.keywords == ["earbuds"]


def test_focused_queries_target_major_earbud_platforms():
    req = QueryUnderstander()._extract_deterministic("earbuds under 1000rs", False)
    queries = QueryGenerator.generate_focused_queries(req)

    assert any("site:flipkart.com" in query for query in queries)
    assert any("site:boat-lifestyle.com" in query for query in queries)


def test_global_currency_budget_is_preserved():
    req = QueryUnderstander()._extract_deterministic("wireless headphones under $250", False)

    assert req.currency == "USD"
    assert req.budget_max == 250.0
