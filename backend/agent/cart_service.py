from __future__ import annotations
import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.models import AgentAuditLog, CheckoutSession
from backend.schemas.cart import AddToCartRequest, AddToCartResponse, CheckoutRequest, CheckoutResponse
from backend.search.verifier import URLVerifier

logger = logging.getLogger("shopping_agent.cart")

# In real-world e-commerce, major platforms require user login sessions and anti-bot protection.
# The agent provides transparent Mode B manual handoff to the real merchant URL, never faking success.
AUTHENTICATED_PARTNER_PLATFORMS: set[str] = set()


class CartService:
    """
    Handles Add-To-Cart and Checkout workflows with strict compliance to:
    1. Transparent Mode A (automation) vs Mode B (manual handoff).
    2. Never faking 'Added to cart'.
    3. Mandatory Human Payment Control barrier (stopping before CVV/OTP/Payment).
    4. Anti-bot and CAPTCHA respect.
    """

    @classmethod
    async def add_to_cart(cls, req: AddToCartRequest, db: Optional[Session] = None) -> AddToCartResponse:
        # 1. URL Verification
        is_valid, status, verified_url = URLVerifier.verify_url(req.product_url)
        if not is_valid:
            return AddToCartResponse(
                status="failed",
                message="Cannot add to cart: Product URL could not be verified.",
                platform=req.platform,
                product_url=req.product_url,
                mode="manual_handoff",
                user_action_needed=True,
            )

        platform_clean = req.platform.lower()

        # 2. Audit logging
        if db:
            try:
                log_entry = AgentAuditLog(
                    user_id=req.user_id,
                    action="ADD_TO_CART_ATTEMPT",
                    payload_json={
                        "product_name": req.product_name,
                        "platform": req.platform,
                        "url": verified_url,
                    },
                )
                db.add(log_entry)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to record audit log: {e}")

        # 3. Check capability: Mode A (Partner API) vs Mode B (Manual Merchant Handoff)
        if platform_clean in AUTHENTICATED_PARTNER_PLATFORMS:
            # Mode A: Permitted automation platform
            logger.info(f"Mode A: Automated cart addition for {req.product_name} on {req.platform}")
            return AddToCartResponse(
                status="success",
                message=f"Successfully added '{req.product_name}' to {req.platform} cart via permitted automation.",
                platform=req.platform,
                product_url=verified_url,
                cart_url=verified_url,
                mode="automated",
                user_action_needed=False,
            )
        else:
            # Mode B: Automation not available or blocked by platform policy
            # Explicit requirement: Do NOT fake success!
            logger.info(f"Mode B: Manual handoff required for {req.platform}")
            return AddToCartResponse(
                status="manual_action_required",
                message="Cart automation is not available for this platform. Opening product page.",
                platform=req.platform,
                product_url=verified_url,
                cart_url=verified_url,
                mode="manual_handoff",
                user_action_needed=True,
            )

    @classmethod
    async def initiate_checkout(cls, req: CheckoutRequest, db: Optional[Session] = None) -> CheckoutResponse:
        """
        Navigates to checkout handoff.
        HARD SECURITY RULE: The agent STOPS before payment. Never handles CVV, OTP, or passwords.
        """
        is_valid, status, verified_url = URLVerifier.verify_url(req.product_url)
        clean_url = verified_url if is_valid else req.product_url

        if db:
            try:
                session_rec = CheckoutSession(
                    user_id=req.user_id,
                    product_id=req.product_id,
                    state="PENDING_HUMAN_PAYMENT_APPROVAL",
                )
                db.add(session_rec)
                audit_rec = AgentAuditLog(
                    user_id=req.user_id,
                    action="CHECKOUT_HUMAN_BARRIER_REACHED",
                    payload_json={
                        "product_name": req.product_name,
                        "platform": req.platform,
                        "url": clean_url,
                        "amount": req.total_amount,
                    },
                )
                db.add(audit_rec)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to record checkout session: {e}")

        return CheckoutResponse(
            status="ready_for_human_approval",
            message=(
                f"Checkout handoff prepared for '{req.product_name}' on {req.platform}. "
                "Agent has stopped at the payment gate. Please review order details and finalize payment."
            ),
            platform=req.platform,
            checkout_url=clean_url,
            requires_human_approval=True,
        )
