"""GitHub issue #246: a user-facing support form that raises a ticket as a
GitHub issue — never in the public `equiCast` repo (where every user's
query/ticker-request/report would be visible to every other user, and to
the internet), always in a separate private repo
(`settings.GITHUB_SUPPORT_REPO`, currently `coldsofttech/equicast-support`)
created specifically for this. `SupportView.post` is the only endpoint
here; there's no read-back — the response is a generic confirmation, not
the created issue's URL/number, since the user has no access to the
private repo to follow it there anyway."""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from identity.authentication import Auth0JWTAuthentication
from identity.throttling import Auth0UserRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from support.throttling import SupportRateThrottle

logger = logging.getLogger(__name__)

#: category -> GitHub label / human-readable prefix, both the same string
#: here for simplicity. Kept in sync with
#: frontend/src/config/supportCategories.json, the same "bundled JSON kept
#: in sync with a backend constant" convention accounts/views.py's
#: ACCOUNT_TYPES already uses for frontend/src/config/accountTypes.json.
CATEGORIES = {
    "query": "Query",
    "ticker-request": "Ticker request",
    "incorrect-data": "Incorrect data",
    "other": "Other",
}

#: Bounds the GitHub issue body — generous enough for a real report, small
#: enough that this can't become a way to upload arbitrary large payloads
#: through a support ticket.
MAX_DESCRIPTION_LENGTH = 4000
MAX_TICKER_LENGTH = 15

#: settings.ENVIRONMENT_NAME -> the GitHub label applied alongside the
#: category label, so an issue in the shared equicast-support repo (same
#: repo for both dev and prod — see that setting's own comment) is
#: distinguishable at a glance. Maps infra's "dev"/"prod" (var.environment)
#: to the label names this repo's labels actually use; an already-matching
#: or unrecognized value (e.g. local dev's default "development") passes
#: through as-is via the .get(..., ENVIRONMENT_NAME) fallback below rather
#: than silently dropping the label.
_ENVIRONMENT_LABELS = {"dev": "development", "prod": "production"}


class GitHubIssueError(Exception):
    """Raised by `_create_github_issue` when the GitHub API call itself
    fails (unconfigured/bad token, network error, non-2xx response) —
    caught by `SupportView.post` to return a clean 502 instead of a raw
    traceback."""


def _create_github_issue(title: str, body: str, labels: list[str]) -> None:
    """POST a new issue to `settings.GITHUB_SUPPORT_REPO`. Uses `urllib`
    (stdlib) rather than adding a `requests` dependency this would be the
    only caller of — the GitHub REST API is plain JSON-over-HTTPS, nothing
    a small dependency-free helper can't do."""
    if not settings.GITHUB_SUPPORT_TOKEN:
        raise GitHubIssueError("GITHUB_SUPPORT_TOKEN is not configured.")

    payload = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{settings.GITHUB_SUPPORT_REPO}/issues",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.GITHUB_SUPPORT_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "equicast-backend",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise GitHubIssueError(f"GitHub API returned {response.status}.")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise GitHubIssueError(str(exc)) from exc


def _build_issue(
    user_id: str, category: str, description: str, ticker: str | None
) -> tuple[str, str]:
    """Return `(title, body)` for the GitHub issue. `title` leads with the
    category and a truncated first line of the description, so the
    private repo's issue list is scannable without opening each one.
    `user_id` (the Auth0 `sub`, already known from the request — no extra
    prompt) is included so the ticket can be correlated back to an
    account without asking the user to repeat who they are, without
    including any actual PII (name/email) the user didn't already choose
    to type into `description` themselves."""
    first_line = description.strip().splitlines()[0][:80]
    title = f"[{CATEGORIES[category]}] {first_line}"
    lines = [f"**Category:** {CATEGORIES[category]}"]
    if ticker:
        lines.append(f"**Ticker:** {ticker}")
    lines.append(f"**Submitted by (user_id):** {user_id}")
    lines.append("")
    lines.append(description.strip())
    return title, "\n".join(lines)


class SupportView(APIView):
    """POST `{"category", "description", "ticker"?}` -> 201 generic
    confirmation, or a 4xx/502 on failure. `category` must be one of
    `CATEGORIES`; `ticker` is only meaningful (and optional even then) for
    `ticker-request`/`incorrect-data`, but accepted for any category
    without complaint — the GitHub issue body simply omits it when unset."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]
    #: Both scopes apply: the general per-minute API budget
    #: (Auth0UserRateThrottle's "user" scope, otherwise applied only via
    #: DEFAULT_THROTTLE_CLASSES) plus SupportRateThrottle's own much
    #: stricter "support" scope — see that class's docstring.
    throttle_classes = [Auth0UserRateThrottle, SupportRateThrottle]

    def post(self, request: Request) -> Response:
        category = request.data.get("category")
        description = request.data.get("description")
        ticker = request.data.get("ticker") or None

        if category not in CATEGORIES:
            return Response(
                {"detail": f"Unknown category. Must be one of: {', '.join(CATEGORIES)}."},
                status=400,
            )
        if not isinstance(description, str) or not description.strip():
            return Response({"detail": "description is required."}, status=400)
        if len(description) > MAX_DESCRIPTION_LENGTH:
            return Response(
                {"detail": f"description must be at most {MAX_DESCRIPTION_LENGTH} characters."},
                status=400,
            )
        if ticker is not None and (not isinstance(ticker, str) or len(ticker) > MAX_TICKER_LENGTH):
            return Response(
                {"detail": f"ticker must be at most {MAX_TICKER_LENGTH} characters."}, status=400
            )

        title, body = _build_issue(request.user.user_id, category, description, ticker)
        environment_label = _ENVIRONMENT_LABELS.get(
            settings.ENVIRONMENT_NAME, settings.ENVIRONMENT_NAME
        )
        try:
            _create_github_issue(title, body, [category, environment_label])
        except GitHubIssueError:
            logger.exception("SupportView.post: failed to create GitHub issue")
            return Response(
                {"detail": "Couldn't submit right now — please try again shortly."}, status=502
            )

        return Response({"detail": "Thanks — we've received this."}, status=201)
