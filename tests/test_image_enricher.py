import asyncio
import html
import json

from backend.schemas.product import Product
from backend.search.image_enricher import ImageEnricher


def _bing_image_result(title, image_url):
    metadata = html.escape(json.dumps({"t": title, "murl": image_url}), quote=True)
    return f'<a class="iusc" m="{metadata}"></a>'


def test_image_enricher_skips_unrelated_results():
    page = "".join([
        _bing_image_result("Wireless mouse", "https://m.media-amazon.com/images/mouse.jpg"),
        _bing_image_result("Sony WH-1000XM5 headphones", "https://m.media-amazon.com/images/headphones.jpg"),
    ])

    image = ImageEnricher._select_relevant_image(page, "Sony WH-1000XM5 headphones")

    assert image == "https://m.media-amazon.com/images/headphones.jpg"


def test_image_enricher_returns_none_without_matching_title():
    page = _bing_image_result("Wireless mouse", "https://m.media-amazon.com/images/mouse.jpg")

    assert ImageEnricher._select_relevant_image(page, "Sony WH-1000XM5 headphones") is None


def test_image_enricher_processes_all_products(monkeypatch):
    async def fake_fetch_product_image(client, query):
        return "https://m.media-amazon.com/images/product.jpg"

    monkeypatch.setattr(ImageEnricher, "fetch_product_image", fake_fetch_product_image)
    products = [
        Product(
            product_name=f"Product model {index}",
            price=100.0,
            url=f"https://store.example/product-{index}",
            source="Store",
            observed_at="2026-10-05T12:00:00Z",
            last_verified_at="2026-10-05T12:00:00Z",
        )
        for index in range(12)
    ]

    enriched = asyncio.run(ImageEnricher.enrich_products(products))

    assert len(enriched) == 12
    assert all(product.image_url for product in enriched)