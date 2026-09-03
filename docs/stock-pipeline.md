# Stock pipeline: deployment and execution

How the `equicast-stock` scheduled ingestion pipeline is built, deployed,
and run. Mirrors [fx-pipeline.md](fx-pipeline.md)'s structure — read that
first if you haven't; this only calls out where stock differs. For local
package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md).

## Architecture

```
packages/stock/config/stocks.dev.yaml   (dev: the tickers to extract)
packages/stock/config/stocks.prod.yaml  (production: the tickers to extract)
        │
        ▼
equicast-stock CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │              ├────▶  equicast-dividends (ex-div date + amount)
        │              ├────▶  equicast-events (earnings/ratings/splits)
        │              └────▶  equicast-metrics (volatility/Sharpe/drawdown/CAGR + fundamentals)
        │                              │
        │                              ▼
        │                       Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet, dividend.parquet, events.parquet, metrics.parquet)
        │
        ▼
GitHub Actions (stock-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/stock/Dockerfile` containerizes the CLI. `stock-image.yml` builds
and pushes it to GHCR as a **private** image (`ghcr.io/<owner>/equicast-stock`).
The ticker config isn't baked in as the only input — tickers can also be
passed at runtime via `--tickers-json`, which is how the scheduled workflow
feeds each parallel chunk its share of the work (see below). The image's
default `CMD` points at `config/stocks.dev.yaml`; `stock-ingestion.yml`
never relies on that default — it resolves `dev`/`prod` itself and always
passes `--tickers-json` explicitly.

`profile()`, `prices()`, dividends (via `equicast-dividends`'
`DividendsClient`), events (via `equicast-events`' `EventsClient`), and
`metrics()`/`fundamentals()` (via `equicast-metrics`) are all implemented.
`equicast-stock` is the only current consumer of `DividendsClient`,
`EventsClient`, and `MetricsClient.fundamentals()` — `equicast-fx` never
calls any of them (fundamentals() raises for FX symbols; FX pairs have no
dividends/earnings/analyst coverage the same way). All three are generic,
symbol-keyed clients rather than `equicast-stock`-specific logic, so a
future ETF package could reuse them the same way.

Expect four `WARNING` lines near the top of every run's logs — a one-time
(per process) disclaimer from `equicast-datafeed`/`StockClient` (data via
yfinance, educational use only), one from `equicast-dividends` (dividend
data via yfinance), one from `equicast-events` (earnings/rating/split data
via yfinance), and one from `equicast-metrics` (metrics calculated by
equicast, not independently verified). Each uses distinct message text, so
none get deduped away by another package's disclaimer already having fired
earlier in the same process. See the [README's disclaimer
section](../README.md#disclaimer) for the full text; this is expected, not
an error.

## Running the CLI locally

```bash
cd packages/stock
uv run equicast-stock --config config/stocks.dev.yaml --out ./output
uv run equicast-stock --tickers-json '["AAPL"]' --out ./output
```

For each ticker this writes:

- `stock=<TICKER>/profile.parquet` — one row: name, quote type, exchange,
  currency, description, sector, industry, website, beta, payout ratio,
  dividend rate/yield, market cap, volume, day open/high/low/close/average,
  year open/high/low/close/average, 50-/200-day moving averages (same
  fields/logic as `equicast-fx`'s profile), address, country, region,
  full-time employees, CEO(s) (each with a name and role), IPO date, last
  updated, source
- `stock=<TICKER>/price/current.parquet` — one row per trading day, for
  the current year only by default: ticker, currency, date,
  open/high/low/close/average, last updated, source
- `stock=<TICKER>/year=<YYYY>/dividend.parquet` — one row per ex-dividend
  date, this year to date by default: ticker, currency, ex_dividend_date,
  price (the dividend amount per share, not a stock price), last updated,
  source. No `payment_date` — yfinance's dividend history has none. Not
  written for tickers/years with no dividends.
- `stock=<TICKER>/year=<YYYY>/events.parquet` — one row per event, this
  year to date plus any future-dated entries by default (only earnings
  ever has any): ticker, event_type (earnings/rating/split), date, plus
  that type's fields (eps_estimate/reported_eps/surprise_pct for earnings;
  firm/from_grade/to_grade/action for ratings; ratio for splits), last
  updated, source. Not written for tickers/years with none of the three.
- `stock=<TICKER>/metrics.parquet` — one row, combining
  `equicast-metrics`' risk/performance metrics (volatility, Sharpe ratio,
  max drawdown, CAGR) with its stock-only fundamentals (PE, EPS, PEG,
  price-to-book/sales, EV/EBITDA, margins, returns, debt-to-equity, FCF/share)

See [packages/stock/README.md](../packages/stock/README.md) for the exact
field lists, including how `address`, `ceos`, and `ipo_date` are derived
(the latter two best-effort — yfinance has no dedicated fields for either),
and how `metrics.parquet` merges the two `equicast-metrics` calls.

Add `--full-load` to fetch each ticker's entire available yfinance history
for **prices, dividends, and events**: prices additionally get
`stock=<TICKER>/price/history.parquet` — every year before the current one,
combined into that one file rather than split per year
(`price/current.parquet` still gets just the current year) — while
dividends and events still write one `dividend.parquet`/`events.parquet`
per year found (current year included). It does not affect
`profile.parquet`/`metrics.parquet`:

```bash
uv run equicast-stock --config config/stocks.dev.yaml --out ./output --full-load
```

Profile, prices, dividends, events, and metrics are fetched as independent
concurrent tasks per ticker (shared across one rate-limited
`DatafeedClient`), tune with:

- `--max-workers` — profile/price/dividend/events/metrics fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/stock/Dockerfile -t equicast-stock:local .
docker run --rm -v "$PWD/output:/output" equicast-stock:local \
  --tickers-json '["AAPL"]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/stock/scripts/smoke_test.py` exercises `StockClient.profile()`,
`.prices()`, `DividendsClient.dividends()`, `EventsClient.events()`,
`MetricsClient.metrics()`/`.fundamentals()`, and the Parquet writers against
**live** Yahoo Finance data — it's a manual QA tool, not part of the
automated `pytest` suite (a live-network test would make CI slow and
flaky), so run it by hand whenever you want to sanity-check the pipeline
end to end.

```bash
cd packages/stock

# Defaults to every ticker in config/stocks.dev.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific tickers
uv run python scripts/smoke_test.py --tickers AAPL,MSFT

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --tickers AAPL --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices, dividends, and events)
uv run python scripts/smoke_test.py --tickers AAPL --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile`, `dividends`, `events`, and `metrics` are
printed in full and `prices` is summarized (row count, date range,
first/last row) rather than dumped in full — a `--full-load` run can be 20+
years of daily rows. `--format parquet` writes the real files via
`write_profile_parquet`/`write_price_parquet`/`write_dividend_parquet`/
`write_events_parquet`/`write_metrics_parquet`, so you can then inspect them
with any Parquet reader (e.g. `pd.read_parquet`).

It also works inside the Docker image — same file is already copied in by
`packages/stock/Dockerfile` — by overriding the image's entrypoint:

```bash
docker build -f packages/stock/Dockerfile -t equicast-stock:local .
docker run --rm --entrypoint uv equicast-stock:local \
  run --no-sync python scripts/smoke_test.py --tickers AAPL

# Parquet mode needs a volume so the output survives the container:
docker volume create smoke-test-vol
docker run --rm --entrypoint uv -v smoke-test-vol:/smoke_output equicast-stock:local \
  run --no-sync python scripts/smoke_test.py --tickers AAPL --format parquet --out /smoke_output
docker run --rm -v smoke-test-vol:/smoke_output alpine find /smoke_output -type f
docker volume rm smoke-test-vol
```

Prefer a named Docker volume over a host bind mount for this on Windows —
Git Bash/PowerShell mangle bare absolute paths like `/smoke_output` passed to
`docker run` (a shell quirk, not a Docker or script issue).

## Deploying the infrastructure

Shares `equicast-market-data-<env>` with `equicast-fx` (`fx=<PAIR>/...` and
`stock=<TICKER>/...` both land in the same bucket) — no separate bucket or
Terraform changes needed. See [fx-pipeline.md's "Deploying the
infrastructure"](fx-pipeline.md#deploying-the-infrastructure) section for the
one-time OIDC role and bucket setup; it already covers this pipeline too
(both AWS-touching workflows authenticate through the same role, and the
IAM policy's `equicast-*` resource wildcard already includes the shared
bucket).

Uses the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo
variables `fx-ingestion.yml` uses (see fx-pipeline.md) — nothing extra to
configure there either.

## Publishing the image

`stock-image.yml` builds and pushes `equicast-stock` to GHCR automatically on
changes to `packages/datafeed/` or `packages/stock/` on `main`, or on demand
via its `workflow_dispatch` trigger (Actions tab → *Build Stock Image* →
*Run workflow*).

## Running the scheduled ingestion

`stock-ingestion.yml` runs once daily, Monday-Friday, at 22:45 UTC
(`cron: "45 22 * * 1-5"`) and can also be triggered manually (Actions tab →
*Stock Ingestion* → *Run workflow*, any day) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each ticker's entire history (all years) of prices/dividends/events instead of just the current year |
| `chunk_size` | `300` | Target stock tickers per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

**Deliberately offset from `etf-ingestion.yml`'s schedule** (`15 22 * * 1-5`
— 22:15 UTC): stock runs 30 minutes after each ETF run (22:45 UTC) — 45
minutes after each FX run — so none of the three pipelines ever overlap
even if an earlier run takes longer than expected. The full chain is FX
(`0 22 * * 1-5`, 22:00 UTC, Monday-Friday — after both US and UK markets
close, see [fx-pipeline.md](fx-pipeline.md#running-the-scheduled-ingestion))
→ +15m → ETF → +30m → stock; all three write into the same S3 bucket and
pull from the same GHCR/Yahoo Finance rate limits.

The scheduled (cron) trigger always targets **production** — same reasoning
as `fx-ingestion.yml`: there's no `environment` input to read on a timer, and
an unattended weekday run should land in the real bucket, not dev. The
`environment` input only applies to manual `workflow_dispatch` runs, where
it defaults to `dev` so an ad-hoc run doesn't write to production by
accident.

The workflow has three jobs, structured identically to `fx-ingestion.yml`'s:

1. **plan** — first resolves the target environment/bucket/config (schedule
   → `production`, dispatch → the `environment` input), failing fast if the
   corresponding `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variable
   isn't set. Then runs `equicast-stock-plan` against `stocks.dev.yaml` or
   `stocks.prod.yaml` (whichever the resolved environment picked) to split
   the configured tickers into chunks, capped at 256 chunks (GitHub's
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
   `equicast-core-build-catalog --asset-class stock` to rebuild
   `catalog/stock.json` — the search catalog `MarketDataClient.search()`
   reads (see [packages/core/README.md](../packages/core/README.md)).
   Needs no S3 permission beyond `ingest`'s existing `s3:PutObject`, since
   it reads the profiles from the downloaded artifacts, not back from S3.

### S3 layout produced

```
s3://equicast-market-data-<env>/
├── catalog/
│   └── stock.json
└── stock=AAPL/
    ├── profile.parquet
    ├── metrics.parquet
    ├── year=2025/dividend.parquet
    ├── year=2025/events.parquet
    ├── year=2026/dividend.parquet
    ├── year=2026/events.parquet
    └── price/
        ├── history.parquet   (every year before 2026, written once by a --full-load run)
        └── current.parquet   (2026, rewritten by every run)
```
