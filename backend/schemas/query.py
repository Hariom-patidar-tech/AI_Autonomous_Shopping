from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class ShoppingRequirements(BaseModel):
    raw_query: str
    category: Optional[str] = None
    product_type: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "INR"
    min_rating: Optional[float] = None
    intent: str = Field(
        default="product_search",
        description="exact_product_search | product_search | comparison | cheapest_search",
    )
    use_case: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    required_attributes: List[str] = Field(default_factory=list)
    preferred_attributes: List[str] = Field(default_factory=list)
    is_hindi_hinglish: bool = False


class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    user_id: Optional[int] = 1
    budget_max: Optional[float] = None
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    min_rating: Optional[float] = None
    sort_by: Optional[str] = "relevance"  # relevance | price_asc | price_desc | rating
