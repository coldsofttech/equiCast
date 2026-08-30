# equicast-core

Generic reader for equicast's S3 market-data layout — the Parquet files
written by `equicast-fx`/`equicast-stock`/`equicast-etf`
(`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/year=<YYYY>/price.parquet`).

Not a data source itself and has no `yfinance`/pandas dependency — just
`boto3` (S3) and `pyarrow` (Parquet parsing) — built generically enough for
any consumer (Django backend, a Lambda function, a script), not tied to
Django.

## Usage

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

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
