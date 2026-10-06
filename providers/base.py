from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class NormalizedProduct(BaseModel):
    """
    Standard normalized schema across all providers.
    Zero mock, dummy, or fabricated data.
    """
    product_id: str = Field(..., description="Retailer unique product/item ID or SKU/ASIN")
    name: str = Field(..., description="Real verified product title")
    brand: Optional[str] = Field(default=None, description="Product brand name")
    model: Optional[str] = Field(default=None, description="Product model identifier")
    variant: Optional[str] = Field(default=None, description="Product variant like color or size")
    price: float = Field(..., gt=0, description="Real verified selling price")
    currency: str = Field(default="INR", description="ISO currency code, defaults to INR")
    thumbnail: str = Field(..., description="Real image URL of the product")
    retailer: str = Field(..., description="Retailer or platform name (e.g. Amazon, Flipkart)")
    product_url: str = Field(..., description="Direct exact product/detail page URL")
    availability: bool = Field(default=True, description="Stock availability status")
    verified: bool = Field(default=True, description="Strict verification status")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "variant": self.variant,
            "price": self.price,
            "currency": self.currency,
            "thumbnail": self.thumbnail,
            "retailer": self.retailer,
            "product_url": self.product_url,
            "availability": self.availability,
            "verified": self.verified,
        }


class BaseProvider(ABC):
    """Abstract connector for all product and search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider credentials/network are configured and usable."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        requirements: Optional[Any] = None,
    ) -> List[NormalizedProduct]:
        """Search and return normalized real products."""
        pass

    @abstractmethod
    def get_status_message(self) -> str:
        """Return user-facing provider status or reason if unavailable."""
        pass
