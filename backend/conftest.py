import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_django_cache():
    """DRF's per-user throttling (identity.throttling.Auth0UserRateThrottle)
    counts requests through Django's cache (CACHES in settings.py) — without
    this, every test authenticating as the same fixture user_id
    ("auth0|abc123") shares one throttle counter across the whole test run,
    so a test late in the run can trip a 429 that has nothing to do with
    what it's actually testing."""
    cache.clear()
    yield
    cache.clear()
