from identity.throttling import Auth0UserRateThrottle


class SupportRateThrottle(Auth0UserRateThrottle):
    """A dedicated, much lower cap on top of the global per-user API rate
    limit (`Auth0UserRateThrottle`'s own `"user"` scope, applied to every
    view via `DEFAULT_THROTTLE_CLASSES` — see settings.py). GitHub issue
    #246's support form creates a real GitHub issue per submission in the
    private `settings.GITHUB_SUPPORT_REPO` — the general per-minute API
    budget is much too generous for that, so `SupportView` adds this scope
    (`"support"`, rate set via `DEFAULT_THROTTLE_RATES`) explicitly on top
    of it, rather than replacing it."""

    scope = "support"
