from __future__ import annotations
import ipaddress
import re
import logging
from typing import Tuple, Optional
from urllib.parse import urlparse

logger = logging.getLogger("shopping_agent.verifier")

TRUSTED_COMMERCE_DOMAINS = {
    "amazon.in",
    "amazon.com",
    "flipkart.com",
    "croma.com",
    "reliancedigital.in",
    "tatacliq.com",
    "myntra.com",
    "ajio.com",
    "meesho.com",
    "nykaa.com",
    "boat-lifestyle.com",
    "gonoise.com",
    "fireboltt.com",
    "boultaudio.com",
    "ptron.in",
    "apple.com",
    "samsung.com",
    "mi.com",
    "lenovo.com",
    "dell.com",
    "hp.com",
    "gadgets360.com",
    "91mobiles.com",
    "smartprix.com",
    "mysmartprice.com",
}

BLOCKED_PATTERNS = [
    r"localhost",
    r"127\.0\.0\.1",
    r"^file://",
    r"^javascript:",
    r"example\.com",
    r"test\.com",
]


class URLVerifier:
    """Deterministic URL verification ensuring no guessed slugs or fake addresses."""

    @staticmethod
    def verify_url(raw_url: Optional[str]) -> Tuple[bool, str, str]:
        """
        Returns: (is_valid, verification_status, cleaned_url)
        verification_status: 'verified' | 'partially_verified' | 'unverified'
        """
        if not raw_url or not isinstance(raw_url, str):
            return False, "unverified", ""

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "unverified", ""

        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f"Blocked invalid/suspicious URL: {url}")
                return False, "unverified", ""

        try:
            parsed = urlparse(url)
            if parsed.username or parsed.password or not parsed.hostname:
                return False, "unverified", ""
            domain = parsed.hostname.lower().rstrip(".").removeprefix("www.")
            if not domain or "." not in domain:
                return False, "unverified", ""
            if domain.endswith((".localhost", ".local", ".internal")):
                return False, "unverified", ""
            try:
                if not ipaddress.ip_address(domain).is_global:
                    return False, "unverified", ""
            except ValueError:
                pass

            # Check if domain is a recognized shopping or retail/tech domain
            is_known_commerce = any(
                domain == trusted or domain.endswith("." + trusted)
                for trusted in TRUSTED_COMMERCE_DOMAINS
            )
            if is_known_commerce:
                return True, "verified", url

            # Google Search Grounding redirect links are verified Google results
            if domain == "google.com" or domain.endswith(".google.com") or domain == "vertexaisearch.cloud.google.com":
                return True, "verified", url

            # General valid web URL
            return True, "partially_verified", url

        except Exception as exc:
            logger.warning(f"URL parsing failed for {url}: {exc}")
            return False, "unverified", ""

    @staticmethod
    def is_product_page_url(raw_url: Optional[str]) -> bool:
        if not raw_url:
            return False
        try:
            parsed = urlparse(raw_url)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                return False
            if parsed.username or parsed.password:
                return False
            host = parsed.hostname.lower().rstrip(".").removeprefix("www.")
            segments = [part.lower() for part in parsed.path.split("/") if part]
            if not segments:
                return False

            blocked_routes = {
                "search", "s", "category", "categories", "collections", "brands",
                "stores", "shop", "deals", "offers", "cart", "checkout", "products",
                "department", "customer", "help", "about", "blog", "news",
            }
            if segments[0] in blocked_routes:
                if segments[0] == "products" and len(segments) > 1:
                    pass
                else:
                    return False

            if URLVerifier._matches_domain(host, "amazon.com") or URLVerifier._matches_domain(host, "amazon.in"):
                return bool(re.search(r"/(?:dp|gp/product|gp/aw/d)/[a-z0-9]{6,}", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "flipkart.com"):
                return bool(re.search(r"/p/[a-z0-9]+", parsed.path, re.I))
            if any(URLVerifier._matches_domain(host, d) for d in ("boat-lifestyle.com", "gonoise.com", "fireboltt.com", "boultaudio.com", "ptron.in")):
                return bool(re.search(r"/products/[a-z0-9\-]+", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "croma.com"):
                return bool(re.search(r"/p/\d+", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "reliancedigital.in"):
                return bool(re.search(r"/p/[a-z0-9\-]+", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "walmart.com"):
                return bool(re.search(r"/ip/[^/]+/\d+", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "ebay.com"):
                return bool(re.search(r"/itm/(?:[^/]+/)?\d+", parsed.path, re.I))
            if URLVerifier._matches_domain(host, "bestbuy.com"):
                return bool(re.search(r"/site/[^/]+/\d+\.p", parsed.path, re.I))

            retailer_domains = (
                "amazon.in", "amazon.com", "flipkart.com", "croma.com", "reliancedigital.in",
                "walmart.com", "bestbuy.com", "ebay.com",
            )
            if any(domain in host for domain in retailer_domains):
                return False

            query_keys = {part.split("=", 1)[0].lower() for part in parsed.query.split("&") if "=" in part}
            if query_keys & {"q", "query", "search", "keyword", "keywords", "k"}:
                return False
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _matches_domain(host: str, domain: str) -> bool:
        return host == domain or host.endswith("." + domain)


class ImageVerifier:
    """Deterministic Image verification ensuring no generic stock images or fake URLs."""

    IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg")
    KNOWN_IMAGE_CDNS = (
        "media-amazon.com",
        "images-amazon.com",
        "flixcart.com",
        "croma.com",
        "reliancedigital.in",
        "shopify.com",
        "cdn.shopify.com",
        "myntassets.com",
        "assets.ajio.com",
        "apple.com",
        "samsung.com",
        "mi.com",
        "xiaomi.com",
        "gstatic.com",
        "googleusercontent.com",
        "bing.net",
        "mm.bing.net",
        "bing.com",
        "bbystatic.com",
    )

    @classmethod
    def verify_image(cls, raw_url: Optional[str]) -> Optional[str]:
        """
        If verified, returns clean image URL.
        If unverified or invalid, returns None (never invent image URLs!).
        """
        if not raw_url or not isinstance(raw_url, str):
            return None

        url = raw_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return None

        # Check for placeholder or generic stock images
        lower_url = url.lower()
        host = urlparse(url).hostname or ""
        host = host.lower().rstrip(".").removeprefix("www.")
        if any(bad in lower_url for bad in ["placeholder", "dummy", "default-product", "avatar", "icon"]):
            return None

        # Check extension or CDN or thumbnail parameters
        has_ext = any(ext in lower_url for ext in cls.IMAGE_EXTENSIONS)
        has_cdn = any(host == cdn or host.endswith("." + cdn) for cdn in cls.KNOWN_IMAGE_CDNS)
        has_thumb_param = "th?id=" in lower_url or "pid=" in lower_url or "tse" in lower_url

        if has_ext or has_cdn or has_thumb_param:
            return url

        # If we cannot verify the image, return None
        return None
