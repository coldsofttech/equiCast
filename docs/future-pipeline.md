# Future pipeline: deployment and execution

How the `equicast-future` scheduled ingestion pipeline is built, deployed,
and run. For local package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md). For what the `profile`/`price`/`metrics`
data actually contains, see the root [README](../README.md).

## Architecture

```
packages/future/config/futures.dev.yaml   (dev: the futures to extract)
packages/future/config/futures.prod.yaml  (production: the futures to extract)
        │
        ▼
equicast-future CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │                  └────▶  equicast-metrics (volatility, Sharpe, drawdown, CAGR)
        │                                  │
        │                                  ▼
        │                           Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet, metrics.parquet)
        │
        ▼
GitHub Actions (future-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/future/Dockerfile` containerizes the CLI. `future-image.yml`
builds and pushes it to GHCR as a **private** image
(`ghcr.io/<owner>/equicast-future`). The future config isn't baked in as
the only input — futures can also be passed at runtime via
`--futures-json`, which is how the scheduled workflow feeds each parallel
chunk its share of the work (see below). The image's default `CMD` points
at `config/futures.dev.yaml`; `future-ingestion.yml` never relies on that
default — it resolves `dev`/`prod` itself and always passes
`--futures-json` explicitly.

Expect two `WARNING` lines near the top of every run's logs — a one-time
(per process) disclaimer from `equicast-datafeed` (data via yfinance,
educational use only) and one from `equicast-metrics` (metrics calculated by
equicast, not independently verified). See the [README's disclaimer
section](../README.md#disclaimer) for the full text; this is expected, not
an error.

A future is a single yfinance symbol (like a stock ticker), not a pair
(like FX) — so `equicast-future` has no dividends and no fundamentals, the
same reasoning `equicast-benchmark`/`equicast-fx` use (a futures contract
pays none and has no earnings/balance sheet). `key` (e.g. `"GOLD"`) is a
stable, human-readable S3 partition identifier you choose; `symbol` (e.g.
`"GC=F"`) is the exact yfinance ticker to fetch — see
`packages/future/config/futures.prod.yaml` for the full list.

## Running the CLI locally

```bash
cd packages/future
uv run equicast-future --config config/futures.dev.yaml --out ./output
uv run equicast-future --futures-json '[{"key":"GOLD","symbol":"GC=F"}]' --out ./output
```

For each future this writes:

- `future=<KEY>/profile.parquet` — one row, current snapshot
- `future=<KEY>/price/current.parquet` — one row per trading day, for the
  current year only by default
- `future=<KEY>/metrics.parquet` — one row, volatility/Sharpe/drawdown/CAGR

Add `--full-load` to fetch each future's entire available yfinance history
for **prices**, additionally writing `future=<KEY>/price/history.parquet` —
every year before the current one, combined into that one file rather than
split per year (`price/current.parquet` still gets just the current year).
It does not affect `metrics.parquet`, which always looks back far enough
for `cagr_10y` regardless of this flag:

```bash
uv run equicast-future --futures-json '[{"key":"GOLD","symbol":"GC=F"}]' --out ./output --full-load
```

Profile, prices, and metrics are fetched as independent concurrent tasks per
future (shared across one rate-limited `DatafeedClient`), tune with:

- `--max-workers` — profile/price/metrics fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/future/Dockerfile -t equicast-future:local .
docker run --rm -v "$PWD/output:/output" equicast-future:local \
  --futures-json '[{"key":"GOLD","symbol":"GC=F"}]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/future/scripts/smoke_test.py` exercises `FutureClient.profile()`,
`.prices()`, and `MetricsClient.metrics()` against **live** Yahoo Finance
data — it's a manual QA tool, not part of the automated `pytest` suite (a
live-network test would make CI slow and flaky), so run it by hand whenever
you want to sanity-check the pipeline end to end.

```bash
cd packages/future

# Defaults to every future in config/futures.dev.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific futures
uv run python scripts/smoke_test.py --futures GOLD:GC=F,SILVER:SI=F

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --futures GOLD:GC=F --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices only)
uv run python scripts/smoke_test.py --futures GOLD:GC=F --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile` and `metrics` are printed in full and
`prices` is summarized (row count, date range, first/last row) rather than
dumped in full — a `--full-load` run can be 20+ years of daily rows.
`--format parquet` writes the real files via
`write_profile_parquet`/`write_price_parquet`/`write_metrics_parquet`, so
you can then inspect them with any Parquet reader (e.g. `pd.read_parquet`).

## Deploying the infrastructure

One-time prerequisite: create the OIDC provider and IAM role
`terraform.yml`/`deploy.yml`/`future-ingestion.yml` all authenticate to AWS
through — see [aws-github-oidc-setup.md](aws-github-oidc-setup.md) for the
exact steps.

Second one-time prerequisite: the state bucket `equicast-tf-state`
must exist before `terraform init` will succeed — see
[terraform-state-setup.md](terraform-state-setup.md).

Once that role exists and the `AWS_ROLE_ARN` repo secret is set, deploy the
rest of the infrastructure — see [the FX pipeline docs' "Deploying the
infrastructure"](fx-pipeline.md#deploying-the-infrastructure) for the exact
commands; the same `equicast-market-data-<env>` S3 bucket is shared by
every asset class, future data lands under `future=<KEY>/...` in it, and
the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo variables
`future-ingestion.yml` reads already need to exist for FX/stock/ETF/
benchmark.

## Publishing the image

`future-image.yml` builds and pushes `equicast-future` to GHCR
automatically on changes to `packages/datafeed/` or `packages/future/` on
`main`, or on demand via its `workflow_dispatch` trigger (Actions tab →
*Build Future Image* → *Run workflow*).

## Running the scheduled ingestion

`future-ingestion.yml` runs once daily, Monday-Friday, at 23:15 UTC
(`cron: "15 23 * * 1-5"`) — 15 minutes after `benchmark-ingestion.yml`
(itself offset from `stock-ingestion.yml`/`fx-ingestion.yml`/
`etf-ingestion.yml`, see
[fx-pipeline.md](fx-pipeline.md#running-the-scheduled-ingestion)), so none
of the five ever overlap. Like `benchmark-ingestion.yml`, there's no
Saturday entry — `equicast-future` has no *dividend* forecasting step
(futures pay no dividends), so there was nothing for a weekly run to do
here. Issue #143 (see [Forecasting](#forecasting) below) added
*price-band* forecasting, but it's not yet wired into this workflow
either. Can also be triggered manually (Actions tab → *Future Ingestion*
→ *Run workflow*, any day) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each future's entire history (all years) instead of just the current year |
| `chunk_size` | `300` | Target futures per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

The scheduled (cron) trigger always targets **production** — there's no
`environment` input to read on a timer, and a data feed running unattended
once a weekday should land in the real bucket, not dev. The `environment`
input only applies to manual `workflow_dispatch` runs, where it defaults to
`dev` so an ad-hoc run doesn't write to production by accident.

The workflow has three jobs — **plan**, **ingest**, and **build-catalog** —
with the exact same responsibilities as `fx-ingestion.yml`'s (see
[fx-pipeline.md](fx-pipeline.md#running-the-scheduled-ingestion) for the
full breakdown of each), just against `equicast-future`/`futures.dev.yaml`/
`futures.prod.yaml`/`catalog/future.parquet` instead.

With today's 16 configured futures (the same list in both dev and prod —
unlike stock/ETF/benchmark, there's no ~10,000-instrument scale-up planned
here) this collapses to a single chunk/leg; at hundreds of futures it fans
out automatically.

### S3 layout produced

```
s3://equicast-market-data-<env>/
├── catalog/
│   └── future.parquet
└── future=GOLD/
    ├── profile.parquet
    ├── metrics.parquet
    └── price/
        ├── history.parquet   (written once by a --full-load run)
        └── current.parquet   (rewritten by every run)
```

## Forecasting

GitHub issue #143 added `equicast-forecasting` support for futures —
`--asset-class future --forecast-kind price-bands` — routing each
configured future's own `key` (e.g. `GOLD`) to one of 5 commodity-class
schemas (Precious Metals, Energy, Industrial Metals, Grains, Softs) and
writing `future=<KEY>/forecasting/price_bands.parquet`. Not wired into
this workflow's scheduled runs; see
[packages/forecasting/README.md](../packages/forecasting/README.md#futures-price-band-forecasting)
for the full model. `--forecast-kind dividends` still doesn't apply here —
futures pay no dividends.
