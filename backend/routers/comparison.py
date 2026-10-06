from __future__ import annotations
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ProductRow

router = APIRouter(prefix="/api/comparison", tags=["Comparison"])


class ComparisonRequest(BaseModel):
    product_ids: List[int]


class ComparisonMatrixItem(BaseModel):
    id: int
    product_name: str
    brand: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    seller: Optional[str] = None
    delivery: Optional[str] = None
    specifications: Dict[str, Any] = {}
    offers_count: int = 0
    best_price_platform: str = ""
    url: str = ""


class ComparisonResponse(BaseModel):
    products: List[ComparisonMatrixItem]
    lowest_overall_price: Optional[float] = None
    highest_overall_price: Optional[float] = None
    recommended_product_id: Optional[int] = None
    summary_verdict: str


@router.post("", response_model=ComparisonResponse)
def compare_products(req: ComparisonRequest, db: Session = Depends(get_db)):
    if not req.product_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one product_id must be provided for comparison.",
        )

    rows = db.query(ProductRow).filter(ProductRow.id.in_(req.product_ids)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No matching products found in database.")

    matrix_items: List[ComparisonMatrixItem] = []
    prices: List[float] = []

    for r in rows:
        p_val = float(r.price) if r.price is not None else None
        if p_val is not None:
            prices.append(p_val)

        best_platform = r.source
        if r.offers:
            # find lowest offer
            valid_offers = [o for o in r.offers if o.price is not None]
            if valid_offers:
                lowest_off = min(valid_offers, key=lambda x: float(x.price))
                best_platform = lowest_off.platform

        matrix_items.append(
            ComparisonMatrixItem(
                id=r.id,
                product_name=r.product_name,
                brand=r.brand,
                price=p_val,
                rating=float(r.rating) if r.rating is not None else None,
                seller=r.seller,
                delivery=r.delivery,
                specifications=r.specifications or {},
                offers_count=len(r.offers),
                best_price_platform=best_platform,
                url=r.url,
            )
        )

    lowest_price = min(prices) if prices else None
    highest_price = max(prices) if prices else None

    # Pick recommended product: highest rating with best price
    best_id = None
    if matrix_items:
        # Score = (rating or 3.5) - (normalized price)
        def comp_score(m: ComparisonMatrixItem):
            r_score = (m.rating or 3.5) * 20
            p_score = (m.price or 100000) / 1000.0
            return r_score - p_score

        best_item = max(matrix_items, key=comp_score)
        best_id = best_item.id
        verdict = f"Recommended: '{best_item.product_name}' provides the highest rating-to-price ratio among compared options."
    else:
        verdict = "Comparison complete."

    return ComparisonResponse(
        products=matrix_items,
        lowest_overall_price=lowest_price,
        highest_overall_price=highest_price,
        recommended_product_id=best_id,
        summary_verdict=verdict,
    )
