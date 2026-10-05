from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class AddToCartRequest(BaseModel):
    product_id: Optional[int] = None
    offer_id: Optional[int] = None
    product_name: str
    platform: str
    product_url: str
    user_id: Optional[int] = 1


class AddToCartResponse(BaseModel):
    status: str  # success | manual_action_required | failed
    message: str
    platform: str
    product_url: str
    cart_url: Optional[str] = None
    mode: str  # automated | manual_handoff
    user_action_needed: bool


class CheckoutRequest(BaseModel):
    product_id: Optional[int] = None
    offer_id: Optional[int] = None
    product_name: str
    platform: str
    product_url: str
    user_id: Optional[int] = 1
    total_amount: Optional[float] = None
    currency: str = "INR"


class CheckoutResponse(BaseModel):
    status: str  # ready_for_human_approval | redirected
    message: str
    platform: str
    checkout_url: str
    requires_human_approval: bool = True
    security_notice: str = (
        "HUMAN PAYMENT CONTROL ENFORCED: Agent is blocked from entering payment secrets, "
        "CVV, OTP, or authorizing transactions. Please complete payment securely on the merchant site."
    )
