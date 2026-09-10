from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from identity.authentication import Auth0User
from identity.throttling import Auth0UserRateThrottle

factory = APIRequestFactory()


def _rate_limited_throttle(rate: str) -> Auth0UserRateThrottle:
    """A throttle instance pinned to `rate` (e.g. "2/min") rather than
    whatever settings.py's DEFAULT_THROTTLE_RATES currently says — DRF
    resolves that once, onto a class attribute, the moment
    rest_framework.throttling is first imported (well before any test
    runs), so `override_settings(REST_FRAMEWORK=...)` doesn't retroactively
    change it. Setting `.rate` directly sidesteps that lookup entirely
    (see SimpleRateThrottle.__init__: it only calls `get_rate()` when
    `self.rate` isn't already set)."""
    throttle = Auth0UserRateThrottle()
    throttle.rate = rate
    throttle.num_requests, throttle.duration = throttle.parse_rate(rate)
    return throttle


class Auth0UserRateThrottleGetCacheKeyTests(TestCase):
    def setUp(self) -> None:
        self.throttle = Auth0UserRateThrottle()

    def test_keys_by_user_id_when_authenticated(self) -> None:
        request = factory.get("/")
        request.user = Auth0User(user_id="auth0|abc123")

        key = self.throttle.get_cache_key(request, view=None)

        self.assertIn("auth0|abc123", key)

    def test_different_users_get_different_keys(self) -> None:
        request_a = factory.get("/")
        request_a.user = Auth0User(user_id="auth0|aaa")
        request_b = factory.get("/")
        request_b.user = Auth0User(user_id="auth0|bbb")

        self.assertNotEqual(
            self.throttle.get_cache_key(request_a, view=None),
            self.throttle.get_cache_key(request_b, view=None),
        )

    def test_falls_back_to_ip_when_unauthenticated(self) -> None:
        # No `.user` at all — the same as a request DRF hasn't attached an
        # authenticator's result to (see Auth0JWTAuthentication.authenticate
        # returning None for a missing/invalid Authorization header).
        request = factory.get("/", REMOTE_ADDR="203.0.113.5")

        key = self.throttle.get_cache_key(request, view=None)

        self.assertIn("203.0.113.5", key)


class Auth0UserRateThrottleAllowRequestTests(TestCase):
    """Exercises `allow_request` directly (real cache reads/writes via
    `get_cache_key`, just a pinned rate — see `_rate_limited_throttle`)
    rather than round-tripping through a view/URL, which would need
    `override_settings(REST_FRAMEWORK=...)` to actually take effect —
    DRF resolves DEFAULT_THROTTLE_RATES onto a class attribute once, at
    first import, well before any test's override could reach it."""

    def test_allows_requests_up_to_the_rate_then_rejects(self) -> None:
        throttle = _rate_limited_throttle("2/min")
        request = factory.get("/")
        request.user = Auth0User(user_id="auth0|abc123")

        self.assertTrue(throttle.allow_request(request, view=None))
        self.assertTrue(throttle.allow_request(request, view=None))
        self.assertFalse(throttle.allow_request(request, view=None))

    def test_different_users_have_independent_budgets(self) -> None:
        throttle = _rate_limited_throttle("1/min")
        request_a = factory.get("/")
        request_a.user = Auth0User(user_id="auth0|first")
        request_b = factory.get("/")
        request_b.user = Auth0User(user_id="auth0|second")

        self.assertTrue(throttle.allow_request(request_a, view=None))
        self.assertFalse(throttle.allow_request(request_a, view=None))
        # A second user's own budget is untouched by the first user's —
        # this is exactly what makes it a *per-user* throttle rather than
        # the separate, deliberately coarse, all-callers-combined API
        # Gateway stage limit.
        self.assertTrue(throttle.allow_request(request_b, view=None))


AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class Auth0UserRateThrottleWiredIntoAViewTests(TestCase):
    """A lighter smoke test than the `allow_request` tests above: proves
    the throttle is actually reached on a real request through a real
    view (not just correct in isolation) — using settings.py's real,
    generous default rate, so this only ever confirms normal traffic
    isn't blocked, not the 429 threshold itself (see the tests above for
    that)."""

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_a_normal_request_is_not_throttled(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_or_create_profile.return_value = {"user_id": "auth0|abc123"}

        response = self.client.get(reverse("me"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
