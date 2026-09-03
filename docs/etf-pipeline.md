# ETF pipeline: deployment and execution

How the `equicast-etf` scheduled ingestion pipeline is built, deployed, and
run. Mirrors [stock-pipeline.md](stock-pipeline.md)'s structure — read that
first if you haven't; this only calls out where ETF differs. For local
package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md).

## Architecture

```
packages/etf/config/etfs.dev.yaml   (dev: the tickers to extract)
packages/etf/config/etfs.prod.yaml  (production: the tickers to extract)
        │
        ▼
equicast-etf CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │              ├────▶  equicast-dividends (ex-div date + amount)
        │              ├────▶  equicast-events (earnings/ratings/splits)
        │              └────▶  equicast-metrics (volatility/Sharpe/drawdown/CAGR)
        │                              │
        │                              ▼
        │                       Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet, dividend.parquet, events.parquet, metrics.parquet)
        │
        ▼
GitHub Actions (etf-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/etf/Dockerfile` containerizes the CLI. `etf-image.yml` builds and
pushes it to GHCR as a **private** image (`ghcr.io/<owner>/equicast-etf`).
The ticker config isn't baked in as the only input — tickers can also be
passed at runtime via `--tickers-json`, which is how the scheduled workflow
feeds each parallel chunk its share of the work (see below). The image's
default `CMD` points at `config/etfs.dev.yaml`; `etf-ingestion.yml` never
relies on that default — it resolves `dev`/`prod` itself and always passes
`--tickers-json` explicitly.

**`profile()`, `prices()`, dividends (via `equicast-dividends`'
`DividendsClient`), events (via `equicast-events`' `EventsClient`), and
risk/performance metrics (via `equicast-metrics`' `MetricsClient.metrics()`)
are all implemented.** `DividendsClient`, `EventsClient`, and
`MetricsClient` are all generic, symbol-keyed clients (not
`equicast-stock`-specific), already consumed by `equicast-stock` —
`equicast-etf` reuses the same ones rather than duplicating logic.
Deliberately **not** `MetricsClient.fundamentals()` — its valuation ratios
are stock-only and mostly `None`/unreliable for ETFs; see
[packages/etf/README.md](../packages/etf/README.md#on-metricsparquet) for
what was actually checked before deciding that. `EventsClient` still
fetches earnings dates and analyst ratings for an ETF ticker, but yfinance
has neither for a fund, so `events.parquet` in practice only ever has
`"split"` rows — checked live for all 5 configured tickers, see
[packages/etf/README.md](../packages/etf/README.md#on-eventsparquet).

Expect four `WARNING` lines near the top of every run's logs — a one-time
(per process) disclaimer from `equicast-datafeed`/`ETFClient` (data via
yfinance, educational use only), one from `equicast-dividends` (dividend
data via yfinance), one from `equicast-events` (earnings/rating/split data
via yfinance), and one from `equicast-metrics` (metrics calculated by
equicast, not independently verified). Each uses distinct message text, so
none get deduped away by another having already fired earlier in the same
process. See the [README's disclaimer section](../README.md#disclaimer) for
the full text; this is expected, not an error.

## Running the CLI locally

```bash
cd packages/etf
uv run equicast-etf --config config/etfs.dev.yaml --out ./output
uv run equicast-etf --tickers-json '["VOO"]' --out ./output
```

For each ticker this writes:

- `etf=<TICKER>/profile.parquet` — one row: name, quote type, exchange,
  currency, description, category, fund family, website, beta, expense
  ratio, dividend rate/yield, total assets, NAV price, volume, day/year
  price range and moving averages, YTD/3yr/5yr average returns, inception
  date, last updated, source
- `etf=<TICKER>/price/current.parquet` — one row per trading day, for
  the current year only by default: ticker, currency, date,
  open/high/low/close/average, last updated, source
- `etf=<TICKER>/dividend/current.parquet` — one row per ex-dividend
  date, for the current year only by default: ticker, currency,
  ex_dividend_date, price (the dividend amount per share, not an ETF
  price), last updated, source. No `payment_date` — yfinance's dividend
  history has none. Not written for a ticker with no dividends this year
  (e.g. `GLD`, a gold trust that pays no distribution).
- `etf=<TICKER>/year=<YYYY>/events.parquet` — one row per event, for the
  current year only by default: ticker, event_type, date, plus that type's
  fields (only `ratio` in practice — see below), last updated, source. Not
  written for tickers/years with no events.
- `etf=<TICKER>/metrics.parquet` — one row, `equicast-metrics`'
  risk/performance metrics only (volatility, Sharpe ratio, max drawdown,
  CAGR) — no valuation/fundamental metrics, unlike `equicast-stock`

See [packages/etf/README.md](../packages/etf/README.md) for the exact field
lists, including how the profile differs from `equicast-stock`'s, how
`website`/`beta`/`inception_date` are derived, why `metrics.parquet` skips
`fundamentals()`, and why `events.parquet` in practice only has `"split"`
rows for an ETF.

Add `--full-load` to fetch each ticker's entire available yfinance history
for **prices, dividends, and events**: prices and dividends additionally
get `etf=<TICKER>/price/history.parquet` and
`etf=<TICKER>/dividend/history.parquet` — every year before the current
one, each combined into that one file rather than split per year
(`price/current.parquet`/`dividend/current.parquet` still get just the
current year) — while events still writes one `events.parquet` per year
found (current year included). It does not affect
`profile.parquet`/`metrics.parquet`:

```bash
uv run equicast-etf --config config/etfs.dev.yaml --out ./output --full-load
```

Profile, prices, dividends, events, and metrics are fetched as independent
concurrent tasks per ticker (shared across one rate-limited
`DatafeedClient`), tune with:

- `--max-workers` — profile/price/dividend/events/metrics fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/etf/Dockerfile -t equicast-etf:local .
docker run --rm -v "$PWD/output:/output" equicast-etf:local \
  --tickers-json '["VOO"]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/etf/scripts/smoke_test.py` exercises `ETFClient.profile()`,
`.prices()`, `DividendsClient.dividends()`, `EventsClient.events()`,
`MetricsClient.metrics()`, and the Parquet writers against **live** Yahoo
Finance data — it's a manual QA tool, not part of the automated `pytest`
suite (a live-network test would make CI slow and flaky), so run it by
hand whenever you want to sanity-check the pipeline end to end.

```bash
cd packages/etf

# Defaults to every ticker in config/etfs.dev.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific tickers
uv run python scripts/smoke_test.py --tickers VOO,QQQ

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --tickers VOO --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices, dividends, and events)
uv run python scripts/smoke_test.py --tickers VOO --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile`, `dividends`, `events`, and `metrics`
are printed in full and `prices` is summarized (row count, date range,
first/last row) rather than dumped in full — a `--full-load` run can be
20+ years of daily rows. `--format parquet` writes the real files via
`write_profile_parquet`/`write_price_parquet`/`write_dividend_parquet`/
`write_events_parquet`/`write_metrics_parquet`, so you can then inspect
them with any Parquet reader (e.g. `pd.read_parquet`).

It also works inside the Docker image — same file is already copied in by
`packages/etf/Dockerfile` — by overriding the image's entrypoint:

```bash
docker build -f packages/etf/Dockerfile -t equicast-etf:local .
docker run --rm --entrypoint uv equicast-etf:local \
  run --no-sync python scripts/smoke_test.py --tickers VOO

# Parquet mode needs a volume so the output survives the container:
docker volume create smoke-test-vol
docker run --rm --entrypoint uv -v smoke-test-vol:/smoke_output equicast-etf:local \
  run --no-sync python scripts/smoke_test.py --tickers VOO --format parquet --out /smoke_output
docker run --rm -v smoke-test-vol:/smoke_output alpine find /smoke_output -type f
docker volume rm smoke-test-vol
```

Prefer a named Docker volume over a host bind mount for this on Windows —
Git Bash/PowerShell mangle bare absolute paths like `/smoke_output` passed to
`docker run` (a shell quirk, not a Docker or script issue).

## Deploying the infrastructure

Shares `equicast-market-data-<env>` with `equicast-fx` and `equicast-stock`
(`fx=<PAIR>/...`, `stock=<TICKER>/...`, and `etf=<TICKER>/...` all land in
the same bucket) — no separate bucket or Terraform changes needed. See
[fx-pipeline.md's "Deploying the infrastructure"](fx-pipeline.md#deploying-the-infrastructure)
section for the one-time OIDC role and bucket setup; it already covers this
pipeline too (all AWS-touching workflows authenticate through the same
role, and the IAM policy's `equicast-*` resource wildcard already includes
the shared bucket).

Uses the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo
variables `fx-ingestion.yml`/`stock-ingestion.yml` use (see
fx-pipeline.md) — nothing extra to configure there either.

## Publishing the image

`etf-image.yml` builds and pushes `equicast-etf` to GHCR automatically on
changes to `packages/datafeed/` or `packages/etf/` on `main`, or on demand
via its `workflow_dispatch` trigger (Actions tab → *Build ETF Image* →
*Run workflow*).

## Running the scheduled ingestion

`etf-ingestion.yml` runs once daily, Monday-Friday, at 22:15 UTC
(`cron: "15 22 * * 1-5"`) and can also be triggered manually (Actions tab →
*ETF Ingestion* → *Run workflow*, any day) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each ticker's entire history (all years) of prices/dividends/events instead of just the current year |
| `chunk_size` | `300` | Target ETF tickers per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

**Deliberately offset from `fx-ingestion.yml`'s schedule** (`0 22 * * 1-5`
— 22:00 UTC, Monday-Friday, after both US and UK markets close — see that
workflow's "Running the scheduled ingestion" for why): ETF runs 15 minutes
after each FX run (22:15 UTC) so the two don't overlap even if FX takes
longer than expected. `stock-ingestion.yml` in turn runs 30 minutes after
this one (`45 22 * * 1-5`, see
[stock-pipeline.md](stock-pipeline.md#running-the-scheduled-ingestion)) — the
full chain is FX → +15m → ETF → +30m → stock, all writing into the same S3
bucket and pulling from the same GHCR/Yahoo Finance rate limits.

The scheduled (cron) trigger always targets **production** — same reasoning
as `fx-ingestion.yml`/`stock-ingestion.yml`: there's no `environment` input
to read on a timer, and an unattended weekday run should land in the real
bucket, not dev. The `environment` input only applies to manual
`workflow_dispatch` runs, where it defaults to `dev` so an ad-hoc run
doesn't write to production by accident.

The workflow has three jobs, structured identically to
`fx-ingestion.yml`/`stock-ingestion.yml`'s:

1. **plan** — first resolves the target environment/bucket/config (schedule
   → `production`, dispatch → the `environment` input), failing fast if the
   corresponding `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variable
   isn't set. Then runs `equicast-etf-plan` against `etfs.dev.yaml` or
   `etfs.prod.yaml` (whichever the resolved environment picked) to split the
   configured tickers into chunks, capped at 256 chunks (GitHub's
   per-workflow matrix job limit).
2. **ingest** — a matrix job (`max-parallel: 20`, tunable in the workflow
   file) with one leg per chunk: pulls the image, passes its chunk via
   `--tickers-json`, uploads the resulting Parquet files to
   `s3://equicast-market-data-<env>/` (the bucket the `plan` job resolved),
   and publishes just its `profile.parquet` files as a short-lived (1 day)
   build artifact for the `build-catalog` job below.
3. **build-catalog** — downloads and merges every leg's artifact from
   **ingest** into one local directory (no single leg ever sees the full
   ticker list, so the catalog can't be built inside one), then runs
   `equicast-core-build-catalog --asset-class etf` to rebuild
   `catalog/etf.json` — the search catalog `MarketDataClient.search()`
   reads (see [packages/core/README.md](../packages/core/README.md)).
   Needs no S3 permission beyond `ingest`'s existing `s3:PutObject`, since
   it reads the profiles from the downloaded artifacts, not back from S3.

### S3 layout produced

```
s3://equicast-market-data-<env>/
├── catalog/
│   └── etf.json
└── etf=VOO/
    ├── profile.parquet
    ├── metrics.parquet
    ├── year=2013/events.parquet
    ├── price/
    │   ├── history.parquet   (every year before 2026, written once by a --full-load run)
    │   └── current.parquet   (2026, rewritten by every run)
    └── dividend/
        ├── history.parquet   (every year before 2026, written once by a --full-load run)
        └── current.parquet   (2026, rewritten by every run)
```
