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

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
