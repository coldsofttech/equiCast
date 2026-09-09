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
  dividend rate/yield, dividend frequency (weekly/monthly/quarterly/
  half_yearly/yearly/irregular/not_applicable, derived from dividend
  history — see [packages/dividends/README.md](../packages/dividends/README.md#dividend_frequency)),
  market cap, volume, day open/high/low/close, year open/high/low/close
  (same fields/logic as `equicast-fx`'s profile), address, country, region,
  full-time employees, CEO(s) (each with a name and role), IPO date, last
  updated, source
- `stock=<TICKER>/price/current.parquet` — one row per trading day, for
  the current year only by default: ticker, currency, date,
  open/high/low/close/average, last updated, source
- `stock=<TICKER>/dividend/current.parquet` — one row per ex-dividend
  date, this year to date by default: ticker, currency, ex_dividend_date,
  price (the dividend amount per share, not a stock price), last updated,
  source. No `payment_date` — yfinance's dividend history has none. Not
  written for a ticker with no dividends this year.
- `stock=<TICKER>/events/current.parquet` — one row per event, this
  year to date plus any future-dated entries by default (only earnings
  ever has any): ticker, event_type (earnings/rating/split), date, plus
  that type's fields (eps_estimate/reported_eps/surprise_pct for earnings;
  firm/from_grade/to_grade/action for ratings; ratio for splits), last
  updated, source. Not written for a ticker with none of the three this
  year or later.
- `stock=<TICKER>/metrics.parquet` — one row, combining
  `equicast-metrics`' risk/performance metrics (volatility, Sharpe ratio,
  max drawdown, CAGR) with its stock-only fundamentals (PE, EPS, PEG,
  price-to-book/sales, EV/EBITDA, margins, returns, debt-to-equity, FCF/share)
- `stock=<TICKER>/forecasting/dividends.parquet` — one row per projected
  future ex-dividend date, up to `--years` (default 10) years out, via
  `equicast-forecasting` (see
  [packages/forecasting/README.md](../packages/forecasting/README.md)).
  Rewritten wholesale from that run's freshly-fetched dividend history —
  not split into history/current — and not written at all for a ticker
  with no dependable payout cadence to extend (an `"irregular"`/
  `"not_applicable"` payer, same cases `dividend_frequency()` flags)

See [packages/stock/README.md](../packages/stock/README.md) for the exact
field lists, including how `address`, `ceos`, and `ipo_date` are derived
(the latter two best-effort — yfinance has no dedicated fields for either),
and how `metrics.parquet` merges the two `equicast-metrics` calls.

Add `--full-load` to fetch each ticker's entire available yfinance history
for **prices, dividends, and events**: all three additionally get a
`history.parquet` — `stock=<TICKER>/price/history.parquet`,
`stock=<TICKER>/dividend/history.parquet`, and
`stock=<TICKER>/events/history.parquet` — every year before the current
one, each combined into that one file rather than split per year
(`price/current.parquet`/`dividend/current.parquet`/`events/current.parquet`
still get the current year — for events, current year *or later*, since
earnings dates can be future-dated). It does not affect
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

`stock-ingestion.yml` runs on two schedules and can also be triggered
manually (Actions tab → *Stock Ingestion* → *Run workflow*, any day):

- Monday-Friday at 22:45 UTC (`cron: "45 22 * * 1-5"`) — the regular
  **ingest** run: `equicast-stock` only, no forecasting.
- Saturday at 22:45 UTC (`cron: "45 22 * * 6"`) — a **forecasting-only**
  run: `equicast-forecasting` only, no `equicast-stock`, no catalog rebuild.
  Forecasting is a full recompute from whatever dividend history is already
  on file, not new market data, so once a week is enough — running it
  Monday-Friday alongside the regular ingest would just repeat the same
  projection five times over.

Which mode a run is in is resolved once, in the `plan` job (see below), from
the day of the week (schedule) or the `forecast_only` input (dispatch) —
every `ingest` matrix leg reads that same resolved mode rather than each
recomputing it.

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each ticker's entire history (all years) of prices/dividends/events instead of just the current year. Ignored when `forecast_only` is set |
| `chunk_size` | `300` | Target stock tickers per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |
| `forecast_years` | `10` | Dividend forecast horizon in years (`equicast-forecasting`'s `--years`). Only used when forecasting actually runs (Saturday, or a manual run with `forecast_only`) |
| `forecast_only` | `false` | Run only `equicast-forecasting` for this dispatch, skipping the regular ingest — mirrors the Saturday schedule, useful for testing forecasting on demand |

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
   isn't set, and also resolves the run mode: `run_ingest`/`run_forecasting`
   — both from the day of the week on a schedule trigger (Saturday, ISO
   weekday 6, forecasts; any other day ingests) or from the `forecast_only`
   input on a dispatch trigger. Then runs `equicast-stock-plan` against
   `stocks.dev.yaml` or `stocks.prod.yaml` (whichever the resolved
   environment picked) to split the configured tickers into chunks, capped
   at 256 chunks (GitHub's per-workflow matrix job limit) — the same chunks
   feed either mode's `--tickers-json` below.
2. **ingest** — a matrix job (`max-parallel: 20`, tunable in the workflow
   file) with one leg per chunk. When `run_ingest` is true: pulls the
   `equicast-stock` image and extracts the chunk's
   profiles/prices/dividends/events/metrics. When `run_forecasting` is true:
   pulls the `equicast-forecasting` image and forecasts the same chunk's
   future dividend payouts (its own independent `DividendsClient` fetch, not
   a read-back of `dividend.parquet`) — into the same `/output` directory,
   so on a normal weekday only the first happens and on Saturday only the
   second does. Either way, uploads whatever landed in `/output` to
   `s3://equicast-market-data-<env>/` (the bucket the `plan` job resolved),
   and — only when `run_ingest` was true, since a forecasting-only run wrote
   no `profile.parquet` — publishes the chunk's profiles as a short-lived
   (1 day) build artifact for the `build-catalog` job below.
3. **build-catalog** — skipped entirely when `run_ingest` is false (nothing
   new to rebuild the catalog from). Otherwise downloads and merges every
   leg's artifact from **ingest** into one local directory (no single leg
   ever sees the full ticker list, so the catalog can't be built inside one),
   then runs
   `equicast-core-build-catalog --asset-class stock` to rebuild
   `catalog/stock.parquet` — the search catalog `MarketDataClient.search()`
   reads (see [packages/core/README.md](../packages/core/README.md)).
   Needs no S3 permission beyond `ingest`'s existing `s3:PutObject`, since
   it reads the profiles from the downloaded artifacts, not back from S3.

### S3 layout produced

```
s3://equicast-market-data-<env>/
├── catalog/
│   └── stock.parquet
└── stock=AAPL/
    ├── profile.parquet
    ├── metrics.parquet
    ├── price/
    │   ├── history.parquet   (every year before 2026, written once by a --full-load run)
    │   └── current.parquet   (2026, rewritten by every run)
    ├── dividend/
    │   ├── history.parquet   (every year before 2026, written once by a --full-load run)
    │   └── current.parquet   (2026, rewritten by every run)
    ├── events/
    │   ├── history.parquet   (every year before 2026, written once by a --full-load run)
    │   └── current.parquet   (2026 or later, rewritten by every run)
    └── forecasting/
        └── dividends.parquet   (rewritten wholesale by every run, not history/current-split)
```

## Forecasting

`equicast-forecasting` now runs two independent kinds of forecast against
`equicast-stock`'s tickers, selected via its `--forecast-kind` flag
(**required** as of GitHub issue #66 — any existing invocation missing it
will fail):

- **`--forecast-kind dividends`** — the pre-existing dividend payout
  projection this doc's own "Running the scheduled ingestion" section
  above describes (the Saturday `equicast-forecasting` run in
  `stock-ingestion.yml`), writing `forecasting/dividends.parquet`. That
  workflow step now passes `--forecast-kind dividends` explicitly.
- **`--forecast-kind price-bands`** (GitHub issue #66) — daily 10th/50th/
  90th-percentile price probability bands, routed through one of 16
  sector/sub-sector schemas (GARCH+EWMA-fallback short horizon, Monte
  Carlo bootstrap medium/long, with a real valuation-reversion bias for
  most sectors at the long horizon), writing `forecasting/
  price_bands.parquet`. See
  [packages/forecasting/README.md](../packages/forecasting/README.md#stock-price-band-forecasting)
  for the full model. **Not yet wired into `stock-ingestion.yml` or any
  scheduled workflow** — run it by hand for now:

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class stock --forecast-kind price-bands --config ../stock/config/stocks.dev.yaml --out ./output
```

Per the issue's "fail loudly" requirement, a ticker whose sector/industry
matches none of the 16 schemas raises `UnroutableSectorError` — the CLI
catches it per-ticker (so the rest of the batch still runs and writes
normally) but re-raises a summary `ForecastBatchError` once every ticker
has had its turn, so the CLI process still exits non-zero rather than
silently reporting success with a gap. Today's 9 configured tickers
(AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, QCOM, AVGO) all route
successfully (Technology, Consumer Cyclical, or Communication Services).
