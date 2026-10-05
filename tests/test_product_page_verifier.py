import json

import pytest

from backend.search.base import RawSearchResult
from backend.search.product_page_verifier import ProductPageVerifier
from backend.search.verifier import URLVerifier


PRODUCT_URL = "https://www.amazon.in/dp/B0ABCDE123"
IMAGE_URL = "https://m.media-amazon.com/images/I/earbuds.jpg"


def _product_html(price=899, currency="INR", image=IMAGE_URL):
    product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "boAt Airdopes 141 TWS Earbuds",
        "brand": {"@type": "Brand", "name": "boAt"},
        "model": "Airdopes 141",
        "image": image,
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": "https://schema.org/InStock",
        },
    }
    return f'<script type="application/ld+json">{json.dumps(product)}</script>'


def _raw_result(url=PRODUCT_URL):
    return RawSearchResult(
        title="Buy boAt Airdopes 141 earbuds",
        snippet="Current listing",
        url=url,
        source="Amazon",
    )


def test_verifies_product_page_price_currency_image_and_exact_url():
    product = ProductPageVerifier.from_html(_raw_result(), _product_html(), PRODUCT_URL)

    assert product is not None
    assert product.product_name == "boAt Airdopes 141 TWS Earbuds"
    assert product.brand == "boAt"
    assert product.model == "Airdopes 141"
    assert product.price == 899
    assert product.currency == "INR"
    assert product.source == "Amazon"
    assert product.image_url == IMAGE_URL
    assert product.url == PRODUCT_URL
    assert product.offers[0].url == PRODUCT_URL
    assert product.availability is True


@pytest.mark.parametrize(
    "page_html",
    [
        _product_html(price=None),
        _product_html(currency=""),
        _product_html(image="https://cdn.example.com/placeholder.jpg"),
    ],
)
def test_rejects_missing_or_unverified_offer_data(page_html):
    assert ProductPageVerifier.from_html(_raw_result(), page_html, PRODUCT_URL) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://amazon.in/",
        "https://amazon.in/s?k=earbuds",
        "https://amazon.in/gp/bestsellers/electronics",
        "https://shop.example.com/search?q=earbuds",
        "http://amazon.in/dp/B0ABCDE123",
    ],
)
def test_rejects_homepage_search_category_and_non_https_urls(url):
    assert not URLVerifier.is_product_page_url(url)
    assert ProductPageVerifier.from_html(_raw_result(url), _product_html(), url) is None


def test_rejects_aggregate_price_without_an_exact_offer():
    product_html = _product_html().replace(
        '"price": 899,',
        '"lowPrice": 799, "highPrice": 999, "offerCount": 4,',
    ).replace('"@type": "Offer"', '"@type": "AggregateOffer"')

    assert ProductPageVerifier.from_html(_raw_result(), product_html, PRODUCT_URL) is None