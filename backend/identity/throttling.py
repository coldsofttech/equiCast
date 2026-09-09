"""Per-user DRF request throttling.

Layered with, not a replacement for, API Gateway's own stage-level
throttling (see infra/modules/api_gateway/main.tf) — that one is a single
aggregate ceiling across every caller combined, since a Lambda-proxied HTTP
API can't see (or bill) individual clients the way a REST API's usage
plans/API keys can. This class is what actually stops one user from
exhausting that shared aggregate budget for everyone else: DRF's own
`django.core.cache`-backed throttle count is keyed per caller (see
`get_cache_key` below), applied globally via DEFAULT_THROTTLE_CLASSES/
DEFAULT_THROTTLE_RATES (see settings.py), so it runs the same way on every
DRF view without each one opting in individually.

Correct only within one warm Lambda execution environment — DRF's
throttle counters live in Django's cache (`CACHES` in settings.py,
currently `LocMemCache`, a plain in-process dict), which is *not* shared
across the several execution environments that can run concurrently under
real traffic. A given user's effective rate can therefore multiply by
however many containers happen to be warm at once. Accepted for now given
this app's actual traffic volume (see settings.py's CACHES comment) —
upgrading to a shared store (e.g. a DynamoDB-backed counter, the same
on-demand pattern `UserProfileClient` already uses) is the documented
upgrade path if that ever stops being good enough, not something this
class needs to change for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.throttling import SimpleRateThrottle

if TYPE_CHECKING:
    # Deferred: rest_framework.views itself resolves DEFAULT_THROTTLE_CLASSES
    # (and so imports this module) while APIView's own class body is still
    # executing — a top-level `from rest_framework.views import APIView`
    # here would be a circular import at runtime. Harmless under
    # `from __future__ import annotations`, which never evaluates this at
    # import time, only for a type checker.
    from rest_framework.request import Request
    from rest_framework.views import APIView


class Auth0UserRateThrottle(SimpleRateThrottle):
    """Keyed by the caller's Auth0 `sub` (`request.user.user_id` — see
    `identity.authentication.Auth0User`), not DRF's own `UserRateThrottle`:
    that keys off `request.user.pk`, which `Auth0User` doesn't have (no
    `django.contrib.auth` user table is involved here — identity lives in
    Auth0). Falls back to the caller's IP for the rare unauthenticated
    case, same as DRF's own `AnonRateThrottle` would — in practice this
    path is never reached today, since every real DRF view already
    requires `IsAuthenticated`, and DRF checks permissions before
    throttles; kept anyway as a cheap correctness fallback rather than
    assuming a future view can't relax that.
    """

    scope = "user"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ident = user.user_id
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
