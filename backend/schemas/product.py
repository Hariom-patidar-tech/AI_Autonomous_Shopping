from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.schemas.query import ShoppingRequirements


class ProductOffer(BaseModel):
    id: Optional[int] = None
    platform: str
    seller: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    currency: str = "INR"
    availability: Optional[bool] = None
    delivery: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    observed_at: str
    verification_status: str = "verified"  # verified | partially_verified | unverified
    supported_actions: List[str] = Field(
        default_factory=lambda: ["view_product", "add_to_cart", "buy_now"]
    )
    # Universal schema compatibility aliases
    retailer: Optional[str] = None
    thumbnail: Optional[str] = None
    product_url: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.retailer:
            self.retailer = self.platform
        if not self.thumbnail:
            self.thumbnail = self.image_url
        if not self.product_url:
            self.product_url = self.url


class Product(BaseModel):
    id: Optional[int] = None
    product_name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    price: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    availability: Optional[bool] = None
    delivery: Optional[str] = None
    return_policy: Optional[str] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)
    url: str
    image_url: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    relevance_score: float = 1.0
    is_exact_match: bool = True
    verification_status: str = "verified"
    observed_at: str
    last_verified_at: str
    offers: List[ProductOffer] = Field(default_factory=list)

    # Universal schema compatibility aliases
    name: Optional[str] = None
    thumbnail: Optional[str] = None
    retailer: Optional[str] = None
    product_url: Optional[str] = None
    product_id: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.name:
            self.name = self.product_name
        if not self.thumbnail:
            self.thumbnail = self.image_url
        if not self.retailer:
            self.retailer = self.source
        if not self.product_url:
            self.product_url = self.url
        if not self.product_id:
            self.product_id = str(self.id or self.url)


class PriceComparisonSummary(BaseModel):
    product_name: str
    currency: str = "INR"
    lowest_price: float
    highest_price: float
    price_spread: float
    best_price_platform: str
    offers_compared: int
    recommendation: str


class SearchResponse(BaseModel):
    query: str
    requirements: ShoppingRequirements
    products: List[Product]
    alternatives: List[Product] = Field(default_factory=list)
    total_results: int
    verified_results: int
    sources: List[str]
    data_source: str = "live"  # Strict: ALWAYS 'live'. Zero mock or fallback permitted.
    search_status: str = "success"  # success | no_verified_results | provider_error
    message: Optional[str] = None
    comparison_summary: Optional[PriceComparisonSummary] = None
    platform_comparison: Optional[GlobalComparisonResponse] = None
    timestamp: str


class PlatformComparisonItem(BaseModel):
    platform: str
    product_name: str
    price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    availability: Optional[bool] = None
    currency: str = "INR"
    image_url: Optional[str] = None
    direct_buy_url: str
    delivery_info: Optional[str] = None


class BestDealSummary(BaseModel):
    recommended_platform: str
    currency: str = "INR"
    lowest_price: float
    savings_vs_highest: float


class GlobalComparisonResponse(BaseModel):
    query: str
    matched_product: str
    currency: str = "INR"
    total_sources_found: int
    comparison_results: List[PlatformComparisonItem]
    best_deal_summary: BestDealSummary


SearchResponse.model_rebuild()
