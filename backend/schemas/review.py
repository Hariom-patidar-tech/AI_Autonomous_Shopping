from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class ReviewItem(BaseModel):
    author: Optional[str] = None
    rating: Optional[float] = None
    text: str
    source: str
    date: Optional[str] = None


class ReviewAnalysisRequest(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    reviews: Optional[List[ReviewItem]] = None
    source_url: Optional[str] = None


class ReviewSummary(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    overall_sentiment: str = "Positive"  # Positive | Mixed | Negative | No verified reviews available
    sentiment_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    positive_themes: List[str] = Field(default_factory=list)
    negative_themes: List[str] = Field(default_factory=list)
    common_defects: List[str] = Field(default_factory=list)
    value_for_money: Optional[str] = None
    delivery_issues: Optional[str] = None
    reviews_analyzed_count: int = 0
    evidence_snippets: List[str] = Field(default_factory=list)
    generated_at: str
