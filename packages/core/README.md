# equicast-core

Shared AWS storage clients for equicast — not a data source itself, built
generically enough for any consumer (Django backend, a Lambda function, a
script), not tied to Django.

## `MarketDataClient` — S3 market data

Reads equicast's S3 market-data layout — the Parquet files written by
`equicast-fx`/`equicast-stock`/`equicast-etf`
(`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/year=<YYYY>/price.parquet`). Has no
`yfinance`/pandas dependency — just `boto3` (S3) and `pyarrow` (Parquet
parsing).

```python
from equicast_core import MarketDataClient

client = MarketDataClient(bucket="equicast-market-data-dev")

client.get_profile("stock", "AAPL")
# {"ticker": "AAPL", "name": "Apple Inc.", ...} or None if not configured

client.get_prices("etf", "VOO")
# [{"ticker": "VOO", "date": "2026-01-02", ...}, ...] for the current year,
# or [] if there's no price.parquet for this year yet
```

`get_profile()` returns `None` (not an exception) when the requested
ticker/pair has no `profile.parquet` in the bucket — a real "this symbol
isn't configured" signal, since the ingestion pipelines always produce a
profile snapshot for every ticker they're configured with. `get_prices()`
returns `[]` for the same "not configured" case, but also for a configured
ticker with no trading days recorded yet this year — both look the same
from this client's point of view. Any other S3 error (permissions, bucket
missing, etc.) propagates as a `botocore.exceptions.ClientError` rather
than being swallowed.

Only reads the **current** calendar year's `price.parquet` — no
cross-year listing/concatenation of full history in this client yet.

## `UserProfileClient` — DynamoDB user profiles

Reads and upserts items in equicast's `user-profiles` DynamoDB table (one
item per user, keyed by `user_id`, no sort key — every access pattern so
far is a point lookup by the caller's own ID). Backs the Django backend's
Auth0-authenticated `/api/identity/me/` endpoint.

```python
from equicast_core import UserProfileClient

client = UserProfileClient(table_name="equicast-user-profiles-dev")

client.get_or_create_profile("auth0|65f2c1...")
# {"user_id": "auth0|65f2c1...", "default_currency": "GBP"}
```

On first login, creates the item with `default_currency="GBP"` (equiCast's
app-level default) via a conditional put
(`attribute_not_exists(user_id)`) — a concurrent first login can't clobber
a profile the user has already started customizing; on that race, the
loser re-fetches and returns the winning write instead.

## `AccountsClient` — S3 JSON user-owned data (accounts)

Reads and writes one user's accounts as a single JSON object in equicast's
user-data S3 bucket, at `accounts/<user_id>.json`. The first of Phase D's
S3-JSON domains — pies, watchlists, and holdings follow the same shape.
Backs the Django backend's Auth0-authenticated `/api/accounts/...`
endpoints.

```python
from equicast_core import AccountsClient

client = AccountsClient(bucket="equicast-user-data-dev")

client.create_account(
    "auth0|65f2c1...",
    name="ISA",
    description="Stocks & shares ISA",
    account_type="ISA",
    currency="GBP",
)
# {"id": "...", "name": "ISA", "description": "Stocks & shares ISA",
#  "account_type": "ISA", "currency": "GBP",
#  "created_at": "...", "updated_at": "..."}

client.list_accounts("auth0|65f2c1...")
client.get_account("auth0|65f2c1...", account_id)
client.update_account("auth0|65f2c1...", account_id, name="Renamed ISA")
client.delete_account("auth0|65f2c1...", account_id)
```

`create_account` raises `AccountLimitExceededError` once a user already has
`max_accounts` accounts — `MAX_ACCOUNTS` (5) by default, overridable per
`AccountsClient` instance via its `max_accounts` constructor arg (the Django
backend sources this from the `MAX_ACCOUNTS` env var, so product can retune
the cap per deployment without a code change). `get_account`/`update_account`/
`delete_account` raise `AccountNotFoundError` for an unknown `account_id`.
Writes use S3 conditional requests (`IfNoneMatch`/`IfMatch` on the object's
ETag) for the same optimistic-concurrency guarantee `UserProfileClient` gets
from DynamoDB's `ConditionExpression` — S3 has no per-field conditional
update, only whole-object conditional puts, so a write that loses the race
is retried against the now-current state rather than clobbering a
concurrent change.

## `PiesClient` — S3 JSON user-owned data (pies)

Same shape as `AccountsClient`: reads and writes one user's pies as a
single JSON object in the user-data S3 bucket, at `pies/<user_id>.json`.
Each pie is nested under an `account_id`; `PiesClient` itself doesn't
validate that the account belongs to the caller — the Django backend's
`pies/views.py` does that, via `AccountsClient.list_accounts`, before
calling `create_pie`. Backs the Django backend's Auth0-authenticated
`/api/pies/...` endpoints.

```python
from equicast_core import PiesClient

client = PiesClient(bucket="equicast-user-data-dev")

client.create_pie(
    "auth0|65f2c1...",
    account_id=account_id,
    name="Core ETFs",
    description="Broad market trackers",
)
# {"id": "...", "account_id": "...", "name": "Core ETFs",
#  "description": "Broad market trackers",
#  "created_at": "...", "updated_at": "..."}

client.list_pies("auth0|65f2c1...")
client.list_pies("auth0|65f2c1...", account_id=account_id)  # scoped to one account
client.get_pie("auth0|65f2c1...", pie_id)
client.update_pie("auth0|65f2c1...", pie_id, name="Renamed pie")
client.delete_pie("auth0|65f2c1...", pie_id)
client.delete_pies_for_account("auth0|65f2c1...", account_id)  # bulk cleanup, returns count removed
```

`create_pie` raises `PieLimitExceededError` once the target `account_id`
already has `max_pies_per_account` pies — `MAX_PIES` (20) by default, and
**per account, not per user** — overridable per `PiesClient` instance via
its `max_pies_per_account` constructor arg (sourced from the `MAX_PIES` env
var the same way `AccountsClient.max_accounts` is). `get_pie`/`update_pie`/
`delete_pie` raise `PieNotFoundError` for an unknown `pie_id`.
`delete_pies_for_account` is a bulk-cleanup helper the Django backend uses
for `DELETE /api/accounts/<id>/?force=true` — it doesn't raise if nothing
matches (an account with no pies is a legitimate no-op, not a missing
single target the way `delete_pie` treats an unknown id). Same S3
conditional-write optimistic concurrency as `AccountsClient`. A pie is
currently just `{id, account_id, name, description, created_at,
updated_at}` — its holdings (see `HoldingsClient` below) live in a separate
S3 object, joined in by the Django backend rather than nested in this one.

## `WatchlistsClient` — S3 JSON user-owned data (watchlists)

Same shape as `AccountsClient`: reads and writes one user's watchlists as a
single JSON object in the user-data S3 bucket, at
`watchlists/<user_id>.json`. Unlike `PiesClient`, a watchlist is **not**
nested under an account — it's user-level, since a user shouldn't need to
create an account just to watchlist a few holdings. Backs the Django
backend's Auth0-authenticated `/api/watchlists/...` endpoints.

```python
from equicast_core import WatchlistsClient

client = WatchlistsClient(bucket="equicast-user-data-dev")

client.create_watchlist(
    "auth0|65f2c1...",
    name="Tech Watch",
    description="Big tech names",
)
# {"id": "...", "name": "Tech Watch", "description": "Big tech names",
#  "created_at": "...", "updated_at": "..."}

client.list_watchlists("auth0|65f2c1...")
client.get_watchlist("auth0|65f2c1...", watchlist_id)
client.update_watchlist("auth0|65f2c1...", watchlist_id, name="Renamed watchlist")
client.delete_watchlist("auth0|65f2c1...", watchlist_id)
```

`create_watchlist` raises `WatchlistLimitExceededError` once a user already
has `max_watchlists` watchlists — `MAX_WATCHLISTS` (5) by default,
overridable per `WatchlistsClient` instance via its `max_watchlists`
constructor arg (sourced from the `MAX_WATCHLISTS` env var the same way
`AccountsClient.max_accounts` is). `get_watchlist`/`update_watchlist`/
`delete_watchlist` raise `WatchlistNotFoundError` for an unknown
`watchlist_id`. Same S3 conditional-write optimistic concurrency as
`AccountsClient`. A watchlist is currently just `{id, name, description,
created_at, updated_at}` — its holdings (see `HoldingsClient` below) live in
a separate S3 object, joined in by the Django backend rather than nested in
this one.

## `HoldingsClient` — S3 JSON user-owned data (holdings)

Same shape as `AccountsClient`: reads and writes one user's holdings as a
single JSON object in the user-data S3 bucket, at `holdings/<user_id>.json`.
A holding hangs off exactly one parent — an `account_id`, a `pie_id`, or a
`watchlist_id` (the other two are always `None`); `HoldingsClient` doesn't
validate that the referenced parent belongs to the caller, or that its
ticker/asset_class has market data — the Django backend's
`holdings/views.py` and `pies/views.py` do that, via
`AccountsClient`/`PiesClient`/`WatchlistsClient` and `MarketDataClient`,
before calling in. Backs the Django backend's Auth0-authenticated
`/api/holdings/...` endpoints and `PUT /api/pies/<id>/holdings/`.

```python
from equicast_core import HoldingsClient

client = HoldingsClient(bucket="equicast-user-data-dev")

# Account-direct or watchlist holdings: plain create/delete, one at a time.
client.create_holding("auth0|65f2c1...", ticker="AAPL", asset_class="stock", account_id=account_id)
# {"id": "...", "ticker": "AAPL", "asset_class": "stock", "account_id": "...",
#  "pie_id": None, "watchlist_id": None, "timestamp": "..."}

client.list_holdings("auth0|65f2c1...")
client.list_holdings("auth0|65f2c1...", account_id=account_id)  # or pie_id=/watchlist_id=
client.get_holding("auth0|65f2c1...", holding_id)
client.delete_holding("auth0|65f2c1...", holding_id)
client.delete_holdings_for_account("auth0|65f2c1...", account_id)  # bulk cleanup
client.delete_holdings_for_watchlist("auth0|65f2c1...", watchlist_id)  # bulk cleanup

# Pie holdings: always an atomic add/remove/reallocate batch — a pie
# represents a 100%-allocated slice of an account, so an independent
# single-item write can't keep its allocation_pct summing to exactly 100.
client.sync_pie_holdings(
    "auth0|65f2c1...",
    pie_id,
    add=[
        {"ticker": "VOO", "asset_class": "etf", "allocation_pct": 60},
        {"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 40},
    ],
)
# [{"id": "...", "ticker": "VOO", ..., "pie_id": "...", "allocation_pct": 60, ...},
#  {"id": "...", "ticker": "VXUS", ..., "pie_id": "...", "allocation_pct": 40, ...}]

client.delete_holdings_for_pies("auth0|65f2c1...", [pie_id, ...])  # bulk cleanup
```

`create_holding` (account/watchlist only — raises `ValueError` if given
neither or both of `account_id`/`watchlist_id`, and doesn't accept `pie_id`
at all) and `sync_pie_holdings` both raise `HoldingAlreadyExistsError` for a
ticker already held in that same parent instance (a ticker *can* repeat
across different parents — two different pies, or a pie and a watchlist —
just not within the same one) and `HoldingLimitExceededError` once that
parent is at its cap: `max_holdings_for_account`/`max_holdings_for_pie`/
`max_holdings_for_watchlist` — `MAX_HOLDINGS_FOR_ACCOUNT` (100)/
`MAX_HOLDINGS_FOR_PIE` (50)/`MAX_HOLDINGS_FOR_WATCHLIST` (20) by default,
each overridable per `HoldingsClient` instance the same way
`AccountsClient.max_accounts` is. `get_holding`/`delete_holding` raise
`HoldingNotFoundError` for an unknown `holding_id`; `delete_holding` also
raises `ValueError` for a pie-scoped holding — those only ever change via
`sync_pie_holdings`, never a standalone delete. `delete_holdings_for_account`/
`delete_holdings_for_pies`/`delete_holdings_for_watchlist` are bulk-cleanup
helpers the Django backend uses for the parent domains' `?force=true`
deletes — like `PiesClient.delete_pies_for_account`, an empty match is a
no-op, not an error.

`sync_pie_holdings` applies an `add`/`remove`/`reallocate` batch to one
pie's holdings atomically — every change is validated against the
resulting state before anything is written, so the whole batch lands in
one write or none of it does. Beyond the errors above, it raises
`HoldingNotFoundError` if a `remove`/`reallocate` id isn't actually one of
the pie's holdings, and `AllocationError` if an `allocation_pct` isn't a
positive number or the resulting holdings (once left non-empty) don't sum
to exactly 100 — parsed via `Decimal` rather than `float` to avoid binary
floating-point sum errors. A pie left with zero holdings (everything
removed) is a valid, unconstrained state; the 100%-sum rule only kicks in
once it holds anything. Same S3 conditional-write optimistic concurrency as
`AccountsClient`.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
