from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.cart import (
    AddToCartRequest,
    AddToCartResponse,
    CheckoutRequest,
    CheckoutResponse,
)
from backend.agent.cart_service import CartService

router = APIRouter(prefix="/api/cart", tags=["Cart & Checkout"])


@router.post("/add", response_model=AddToCartResponse)
async def add_product_to_cart(
    req: AddToCartRequest,
    db: Session = Depends(get_db),
):
    """
    Add to Cart endpoint implementing Mode A (permitted automation)
    and Mode B (transparent manual handoff without faking success).
    """
    return await CartService.add_to_cart(req, db=db)


@router.post("/checkout/approve", response_model=CheckoutResponse)
async def approve_checkout_handoff(
    req: CheckoutRequest,
    db: Session = Depends(get_db),
):
    """
    Prepares checkout handoff while enforcing the Human Payment Control barrier.
    Agent NEVER enters CVV, OTP, or authorizations.
    """
    return await CartService.initiate_checkout(req, db=db)
