"""GitHub issue #246: a user-facing support form that raises a ticket as a
GitHub issue — never in the public `equiCast` repo (where every user's
query/ticker-request/report would be visible to every other user, and to
the internet), always in a separate private repo
(`settings.SUPPORT_REPO`, currently `coldsofttech/equicast-support`)
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

#: category -> human-readable text used in the issue title/body's
#: "**Category:**" line (see _build_issue) — not necessarily the GitHub
#: label applied (see _CATEGORY_LABELS below for where those differ). Kept
#: in sync with frontend/src/config/supportCategories.json, the same
#: "bundled JSON kept in sync with a backend constant" convention
#: accounts/views.py's ACCOUNT_TYPES already uses for
#: frontend/src/config/accountTypes.json.
CATEGORIES = {
    "query": "Query",
    "ticker-request": "Ticker request",
    "incorrect-data": "Incorrect Data",
    "other": "Request",
}

#: Bounds the GitHub issue body — generous enough for a real report, small
#: enough that this can't become a way to upload arbitrary large payloads
#: through a support ticket.
MAX_DESCRIPTION_LENGTH = 4000
MAX_TICKER_LENGTH = 15

#: subject_type -> human-readable text used in the issue body's "**Affected
#: <type>:**" line (see _build_issue) — only meaningful for "incorrect-data"
#: (see SupportView.post), where reporting *what's* wrong requires saying
#: what domain it's about. "other" covers anything not covered by the first
#: four, or when the user doesn't know/can't find the specific item — same
#: role "other" plays in CATEGORIES itself. Kept in sync with
#: frontend/src/config/supportSubjectTypes.json.
SUBJECT_TYPES = {
    "account": "Account",
    "pie": "Pie",
    "goal": "Goal",
    "holding": "Holding",
    "other": "Other",
}

#: Bounds `subject` (the specific account/pie/goal/holding name, or "Other")
#: — generous for any real name, small enough it can't smuggle a large
#: payload through, same reasoning as MAX_TICKER_LENGTH/MAX_DESCRIPTION_LENGTH.
MAX_SUBJECT_LENGTH = 200

#: settings.ENVIRONMENT_NAME -> the GitHub label applied alongside the
#: category label, so an issue in the shared equicast-support repo (same
#: repo for both dev and prod — see that setting's own comment) is
#: distinguishable at a glance. Maps infra's "dev"/"prod" (var.environment)
#: to the label names this repo's labels actually use; an already-matching
#: or unrecognized value (e.g. local dev's default "development") passes
#: through as-is via the .get(..., ENVIRONMENT_NAME) fallback below rather
#: than silently dropping the label.
_ENVIRONMENT_LABELS = {"dev": "development", "prod": "production"}

#: category -> the GitHub label actually applied, when it needs to differ
#: from the category key itself (e.g. this repo's labels are
#: "customer-query"/"customer-issue"/"customer-other", not the API's
#: "query"/"incorrect-data"/"other" values) — same "differs only where
#: needed, falls through as-is otherwise" convention as _ENVIRONMENT_LABELS
#: above. The category key/CATEGORIES stay unchanged (frontend contract,
#: validation, issue title/body all still use "query"/"incorrect-data"/
#: "other"); only the label applied to the created issue is affected.
_CATEGORY_LABELS = {
    "query": "customer-query",
    "incorrect-data": "customer-issue",
    "other": "customer-other",
}


class GitHubIssueError(Exception):
    """Raised by `_create_github_issue` when the GitHub API call itself
    fails (unconfigured/bad token, network error, non-2xx response) —
    caught by `SupportView.post` to return a clean 502 instead of a raw
    traceback."""


def _create_github_issue(title: str, body: str, labels: list[str]) -> None:
    """POST a new issue to `settings.SUPPORT_REPO`. Uses `urllib`
    (stdlib) rather than adding a `requests` dependency this would be the
    only caller of — the GitHub REST API is plain JSON-over-HTTPS, nothing
    a small dependency-free helper can't do."""
    if not settings.SUPPORT_ISSUE_TOKEN:
        raise GitHubIssueError("SUPPORT_ISSUE_TOKEN is not configured.")

    payload = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{settings.SUPPORT_REPO}/issues",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.SUPPORT_ISSUE_TOKEN}",
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
    user_id: str,
    category: str,
    description: str,
    ticker: str | None,
    subject_type: str | None = None,
    subject: str | None = None,
) -> tuple[str, str]:
    """Return `(title, body)` for the GitHub issue. `title` leads with the
    category and a truncated first line of the description — or, when
    description is blank (only possible for "ticker-request", the one
    category where it's optional; see `SupportView.post`), the ticker
    itself — so the private repo's issue list is scannable without opening
    each one. `user_id` (the Auth0 `sub`, already known from the request —
    no extra prompt) is included so the ticket can be correlated back to
    an account without asking the user to repeat who they are, without
    including any actual PII (name/email) the user didn't already choose
    to type into `description` themselves. `subject_type`/`subject` are
    only ever passed for "incorrect-data" (see `SupportView.post`) — which
    specific account/pie/goal/holding (or "Other") the report is about."""
    description = description.strip()
    first_line = description.splitlines()[0][:80] if description else f"Ticker: {ticker}"
    title = f"[{CATEGORIES[category]}] {first_line}"
    lines = [f"**Category:** {CATEGORIES[category]}"]
    if ticker:
        lines.append(f"**Ticker:** {ticker}")
    if subject_type and subject:
        lines.append(f"**Affected {SUBJECT_TYPES[subject_type]}:** {subject}")
    lines.append(f"**Submitted by (user_id):** {user_id}")
    if description:
        lines.append("")
        lines.append(description)
    return title, "\n".join(lines)


class SupportView(APIView):
    """POST `{"category", "description", "ticker"?, "subject_type"?,
    "subject"?}` -> 201 generic confirmation, or a 4xx/502 on failure.
    `category` must be one of `CATEGORIES`. `ticker`/`subject_type`/
    `subject` are all validated (if present) but only ever required for
    one specific category, same "accepted for any category without
    complaint, only sometimes required" shape `ticker` already had before
    `subject_type`/`subject` existed:
    - `ticker-request`: naming the ticker is the whole point, so `ticker`
      is required and `description` becomes optional context.
    - `incorrect-data`: naming *what's* wrong is the whole point, so
      `subject_type` (one of `SUBJECT_TYPES`) and `subject` (the specific
      account/pie/goal/holding name, or "Other") are both required.
      `description` stays required here too, unlike `ticker-request`.
    - every other category: only `description` is required."""

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
        subject_type = request.data.get("subject_type") or None
        subject = request.data.get("subject") or None

        if category not in CATEGORIES:
            return Response(
                {"detail": f"Unknown category. Must be one of: {', '.join(CATEGORIES)}."},
                status=400,
            )

        # "ticker-request"/"incorrect-data" each make one extra field
        # mandatory and, for "ticker-request" only, make description
        # optional — see this class's docstring. Every other category
        # keeps the original shape: description required, everything else
        # optional.
        if category == "ticker-request":
            if not isinstance(ticker, str) or not ticker.strip():
                return Response({"detail": "ticker is required."}, status=400)
        elif category == "incorrect-data":
            if subject_type not in SUBJECT_TYPES:
                return Response(
                    {
                        "detail": (
                            "subject_type is required for incorrect-data and must be one "
                            f"of: {', '.join(SUBJECT_TYPES)}."
                        )
                    },
                    status=400,
                )
            if not isinstance(subject, str) or not subject.strip():
                return Response({"detail": "subject is required for incorrect-data."}, status=400)
            if not isinstance(description, str) or not description.strip():
                return Response({"detail": "description is required."}, status=400)
        elif not isinstance(description, str) or not description.strip():
            return Response({"detail": "description is required."}, status=400)

        if description is not None and (
            not isinstance(description, str) or len(description) > MAX_DESCRIPTION_LENGTH
        ):
            return Response(
                {"detail": f"description must be at most {MAX_DESCRIPTION_LENGTH} characters."},
                status=400,
            )
        if ticker is not None and (not isinstance(ticker, str) or len(ticker) > MAX_TICKER_LENGTH):
            return Response(
                {"detail": f"ticker must be at most {MAX_TICKER_LENGTH} characters."}, status=400
            )
        if subject is not None and (
            not isinstance(subject, str) or len(subject) > MAX_SUBJECT_LENGTH
        ):
            return Response(
                {"detail": f"subject must be at most {MAX_SUBJECT_LENGTH} characters."},
                status=400,
            )

        title, body = _build_issue(
            request.user.user_id, category, description or "", ticker, subject_type, subject
        )
        category_label = _CATEGORY_LABELS.get(category, category)
        environment_label = _ENVIRONMENT_LABELS.get(
            settings.ENVIRONMENT_NAME, settings.ENVIRONMENT_NAME
        )
        try:
            _create_github_issue(title, body, [category_label, environment_label])
        except GitHubIssueError:
            logger.exception("SupportView.post: failed to create GitHub issue")
            return Response(
                {"detail": "Couldn't submit right now — please try again shortly."}, status=502
            )

        return Response({"detail": "Thanks — we've received this."}, status=201)
