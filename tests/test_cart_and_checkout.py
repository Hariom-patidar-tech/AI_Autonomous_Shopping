import pytest
from backend.agent.cart_service import CartService
from backend.schemas.cart import AddToCartRequest, CheckoutRequest
from backend.search.verifier import URLVerifier


@pytest.mark.asyncio
async def test_add_to_cart_mode_b_manual_handoff():
    """Section 22: Platform without automation does NOT fake success, returns manual_action_required."""
    req = AddToCartRequest(
        product_name="Redmi Note 10S",
        platform="Amazon",
        product_url="https://amazon.in/dp/B091J3M",
    )

    res = await CartService.add_to_cart(req)

    assert res.status == "manual_action_required"
    assert "Cart automation is not available for this platform. Opening product page." in res.message
    assert res.mode == "manual_handoff"
    assert res.user_action_needed is True
    assert res.product_url == "https://amazon.in/dp/B091J3M"


@pytest.mark.asyncio
async def test_checkout_human_payment_barrier():
    """Section 24: Agent STOPS before payment. Never handles CVV, OTP, or authorizations."""
    req = CheckoutRequest(
        product_name="iPhone 17 Pro",
        platform="Amazon",
        product_url="https://amazon.in/dp/B091J3M",
        total_amount=129999.0,
    )

    res = await CartService.initiate_checkout(req)

    assert res.status == "ready_for_human_approval"
    assert res.requires_human_approval is True
    assert "HUMAN PAYMENT CONTROL ENFORCED" in res.security_notice
    assert "Agent has stopped at the payment gate" in res.message


def test_url_verifier_rejects_fake_and_malformed_urls():
    """Section 12 & Test K: NEVER construct product URLs from guessed slugs or invalid schemes."""
    # Guessed localhost or invalid scheme
    valid1, _, _ = URLVerifier.verify_url("http://localhost:8000/fake-slug")
    assert valid1 is False

    valid2, _, _ = URLVerifier.verify_url("javascript:alert(1)")
    assert valid2 is False

    valid3, _, _ = URLVerifier.verify_url("example.com/phone")
    assert valid3 is False

    # Valid real e-commerce URL
    valid_real, status, clean = URLVerifier.verify_url("https://www.amazon.in/dp/B098NSD7")
    assert valid_real is True
    assert status == "verified"
    assert clean == "https://www.amazon.in/dp/B098NSD7"
