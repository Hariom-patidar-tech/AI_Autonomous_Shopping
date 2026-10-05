from __future__ import annotations
from typing import Optional
from backend.schemas.product import (
    Product,
    ProductOffer,
    SearchResponse,
    PlatformComparisonItem,
    BestDealSummary,
    GlobalComparisonResponse,
)


def _format_discount(price: Optional[float], original_price: Optional[float]) -> Optional[str]:
    if price is None or original_price is None:
        return None
    if original_price <= 0 or original_price <= price:
        return None
    pct = round(((original_price - price) / original_price) * 100)
    if pct <= 0:
        return None
    return f"{pct}%"


def _item_from_offer(product: Product, offer: ProductOffer) -> PlatformComparisonItem:
    price = float(offer.price) if offer.price is not None else 0.0
    original = offer.original_price
    if original is None:
        original = product.specifications.get("original_price") if isinstance(product.specifications, dict) else None
        if original is not None:
            try:
                original = float(original)
            except (TypeError, ValueError):
                original = None
    return PlatformComparisonItem(
        platform=offer.platform or product.source,
        product_name=product.product_name,
        price=price,
        original_price=float(original) if original is not None else None,
        discount_percentage=_format_discount(price, original if original is not None else None),
        rating=product.rating,
        review_count=product.review_count,
        availability=offer.availability,
        currency=offer.currency,
        image_url=offer.image_url or product.image_url,
        direct_buy_url=offer.url,
        delivery_info=offer.delivery,
    )


def _item_from_product(product: Product) -> PlatformComparisonItem:
    price = float(product.price) if product.price is not None else 0.0
    original = None
    if isinstance(product.specifications, dict):
        raw_orig = product.specifications.get("original_price")
        try:
            original = float(raw_orig) if raw_orig is not None else None
        except (TypeError, ValueError):
            original = None
    return PlatformComparisonItem(
        platform=product.source,
        product_name=product.product_name,
        price=price,
        original_price=original,
        discount_percentage=_format_discount(price, original),
        rating=product.rating,
        review_count=product.review_count,
        availability=product.availability,
        currency=product.currency,
        image_url=product.image_url,
        direct_buy_url=product.url,
        delivery_info=product.delivery,
    )


def build_global_comparison(search_res: SearchResponse) -> GlobalComparisonResponse:
    """Normalize live search output into the React-consumable comparison schema.

    Never invents MRP or discount. Unknown original prices stay null.
    Results are ranked lowest price first.
    """
    items: list[PlatformComparisonItem] = []
    seen_urls: set[str] = set()
    all_candidates = list(search_res.products) + list(search_res.alternatives)

    canonical_title = search_res.query
    currency = "INR"
    if all_candidates:
        canonical_title = all_candidates[0].product_name
        currency = all_candidates[0].currency or "INR"

    for product in all_candidates:
        if product.offers:
            for offer in product.offers:
                url = (offer.url or "").strip()
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                items.append(_item_from_offer(product, offer))
        else:
            url = (product.url or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            items.append(_item_from_product(product))

    items.sort(key=lambda x: (x.currency.upper() != currency.upper(), x.price if x.price > 0 else float("inf")))

    priced = [i.price for i in items if i.currency.upper() == currency.upper() and i.price > 0]
    lowest = priced[0] if priced else 0.0
    highest = max(priced) if priced else 0.0
    rec_platform = next((item.platform for item in items if item.currency.upper() == currency.upper()), "")
    savings = round(highest - lowest, 2) if highest > lowest else 0.0

    return GlobalComparisonResponse(
        query=search_res.query,
        matched_product=canonical_title,
        currency=currency,
        total_sources_found=len(items),
        comparison_results=items,
        best_deal_summary=BestDealSummary(
            recommended_platform=rec_platform,
            currency=currency,
            lowest_price=lowest,
            savings_vs_highest=savings,
        ),
    )
