import pytest
import backend.search.google_provider as google_provider_module
from backend.search.google_provider import GoogleSearchProvider


@pytest.mark.asyncio
async def test_google_provider_quota_cooldown(monkeypatch):
    GoogleSearchProvider._quota_exhausted = True
    GoogleSearchProvider._quota_retry_after = 200.0
    monkeypatch.setattr(google_provider_module.time, "monotonic", lambda: 100.0)
    assert GoogleSearchProvider.quota_cooldown_remaining() == 100
    assert GoogleSearchProvider.quota_exhausted() is True

    monkeypatch.setattr(google_provider_module.time, "monotonic", lambda: 201.0)
    assert GoogleSearchProvider.quota_cooldown_remaining() == 0
    assert GoogleSearchProvider.quota_exhausted() is False
    GoogleSearchProvider._quota_exhausted = False
