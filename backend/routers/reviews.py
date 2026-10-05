from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ProductRow, ReviewSummaryRow
from backend.schemas.review import ReviewAnalysisRequest, ReviewSummary
from backend.agent.review_analyzer import ReviewAnalyzer

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])
analyzer = ReviewAnalyzer()


@router.post("/analyze", response_model=ReviewSummary)
async def analyze_product_reviews(
    req: ReviewAnalysisRequest,
    db: Session = Depends(get_db),
):
    target_name = req.product_name

    # If product_id given, check DB for name
    if req.product_id:
        p_row = db.query(ProductRow).filter(ProductRow.id == req.product_id).one_or_none()
        if p_row:
            target_name = p_row.product_name

    summary = await analyzer.analyze(
        product_name=target_name,
        reviews=req.reviews,
        product_id=req.product_id,
    )

    # Persist summary in DB if product_id exists
    if req.product_id:
        try:
            rec = ReviewSummaryRow(
                product_id=req.product_id,
                sentiment_score=summary.sentiment_score,
                overall_sentiment=summary.overall_sentiment,
                positive_themes=summary.positive_themes,
                negative_themes=summary.negative_themes,
                defects=summary.common_defects,
                value_for_money=summary.value_for_money,
                delivery_issues=summary.delivery_issues,
            )
            db.add(rec)
            db.commit()
        except Exception:
            db.rollback()

    return summary
