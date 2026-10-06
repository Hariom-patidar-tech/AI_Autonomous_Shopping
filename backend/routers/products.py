from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ProductRow
from backend.schemas.product import Product, ProductOffer, SearchResponse, GlobalComparisonResponse
from backend.schemas.query import SearchQueryRequest
from backend.agent.shopping_pipeline import ShoppingPipeline
from backend.agent.platform_comparison import build_global_comparison

router = APIRouter(prefix="/api/products", tags=["Products"])
pipeline = ShoppingPipeline()
logger = logging.getLogger("shopping_agent.api.products")


def _log_search_response(response: SearchResponse) -> SearchResponse:
    logger.info("Final product search JSON: %s", response.model_dump_json())
    return response


@router.get("/search", response_model=SearchResponse)
async def search_products_get(
    query: str = Query(..., min_length=1, description="Natural language search query"),
    budget_max: Optional[float] = Query(None, description="Maximum budget filter"),
    budget_currency: Optional[str] = Query(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"),
    min_rating: Optional[float] = Query(None, description="Minimum rating filter"),
    sort_by: str = Query("relevance", description="relevance | price_asc | price_desc | rating"),
    db: Session = Depends(get_db),
):
    """Universal product search endpoint accepting any natural language or Hindi/Hinglish query."""
    response = await pipeline.run(
        query=query,
        budget_max=budget_max,
        budget_currency=budget_currency,
        min_rating=min_rating,
        sort_by=sort_by,
        db=db,
    )
    return _log_search_response(response)


@router.post("/search", response_model=SearchResponse)
async def search_products_post(
    req: SearchQueryRequest,
    db: Session = Depends(get_db),
):
    """POST endpoint for product search."""
    response = await pipeline.run(
        query=req.query,
        user_id=req.user_id,
        budget_max=req.budget_max,
        budget_currency=req.budget_currency,
        min_rating=req.min_rating,
        sort_by=req.sort_by or "relevance",
        db=db,
    )
    return _log_search_response(response)


@router.get("/compare-platforms", response_model=GlobalComparisonResponse)
async def compare_platforms_endpoint(
    query: str = Query(..., min_length=1, description="Natural language product query to compare across platforms"),
    db: Session = Depends(get_db),
):
    """
    Autonomous global price comparison:
    live multi-platform discovery normalized into a React-consumable JSON schema.
    """
    search_res: SearchResponse = await pipeline.run(query=query, sort_by="price_asc", db=db)
    return build_global_comparison(search_res)


@router.get("/{product_id}", response_model=Product)
def get_product_details(product_id: int, db: Session = Depends(get_db)):
    """Fetch product details by ID, including all verified multi-platform offers."""
    row = db.query(ProductRow).filter(ProductRow.id == product_id).one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    offers = []
    for off in row.offers:
        offers.append(
            ProductOffer(
                id=off.id,
                platform=off.platform,
                seller=off.seller,
                price=float(off.price),
                currency=off.currency,
                availability=off.availability,
                delivery=off.delivery,
                url=off.url,
                image_url=off.image_url,
                observed_at=off.observed_at.isoformat() if off.observed_at else "",
                verification_status=off.verification_status,
                supported_actions=["view_product", "add_to_cart", "buy_now"],
            )
        )

    return Product(
        id=row.id,
        product_name=row.product_name,
        brand=row.brand,
        model=row.model,
        price=float(row.price) if row.price is not None else None,
        currency=row.currency,
        rating=float(row.rating) if row.rating is not None else None,
        review_count=row.review_count,
        seller=row.seller,
        availability=row.availability,
        delivery=row.delivery,
        return_policy=row.return_policy,
        specifications=row.specifications or {},
        url=row.url,
        image_url=row.image_url,
        source=row.source,
        source_url=row.url,
        verification_status=row.verification_status,
        observed_at=row.observed_at.isoformat() if row.observed_at else "",
        last_verified_at=row.last_verified_at.isoformat() if row.last_verified_at else "",
        offers=offers,
    )
