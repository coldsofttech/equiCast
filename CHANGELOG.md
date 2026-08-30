# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `equicast-events` (`packages/events/`): standalone, generic package for
  corporate events (earnings reports, analyst rating changes, stock splits)
  on any yfinance equity-like symbol, built the same way as
  `equicast-dividends`/`equicast-metrics`. `equicast-stock`'s CLI now writes
  `stock=<TICKER>/year=<YYYY>/events.parquet` alongside price/dividend,
  combining all three event types into one file per year via an
  `event_type` discriminator column.
- `equicast-datafeed`: `get_earnings_dates`, `get_upgrades_downgrades`, and
  `get_splits`, backing `equicast-events`.
- Educational-use disclaimers, documented in each package's README
  (`equicast-datafeed`, `equicast-fx`: yfinance-sourced data, not financial
  advice; `equicast-metrics`: calculated by equicast, validate accuracy
  independently) and shown once per process as a console warning —
  `DatafeedClient`/`FXClient` share one disclaimer (deduped by message text,
  via a new `equicast_datafeed.warn_once` helper, so constructing many of
  either doesn't repeat it), `MetricsClient` shows its own. Falls back to
  Python's logging "handler of last resort" (plain stderr output) when
  nothing else has configured a handler, so it's visible either way.
- Initial project scaffold with `equicast`, a core Python package (yfinance
  ingestion, Parquet storage) as the root of a uv workspace.
- Django REST backend (`backend/`) exposing market data at
  `/api/market-data/<ticker>/`, depending on `equicast` via the uv workspace.
- React (Vite) frontend (`frontend/`) with a minimal UI for fetching ticker
  history.
- Terraform configuration (`infra/`) for AWS: S3 market-data bucket, S3
  static-site bucket for the frontend, and an ECR repository for the backend
  image.
- GitHub Actions workflows: backend CI (ruff, mypy, pytest), frontend CI
  (eslint, vitest, build), Terraform plan/apply, and deploy (ECR push + S3
  sync).
- Pre-commit hooks (`.pre-commit-config.yaml`) covering ruff, mypy, and
  pytest (unit) for the core package and Django backend, plus eslint and
  vitest (unit) for the React frontend.
- `equicast-datafeed` (`packages/datafeed/`): standalone package providing a
  resilient yfinance client with rate limiting and retry-with-backoff,
  reusable by any future market-data package.
- `equicast-fx` (`packages/fx/`): standalone, class-based package for
  extracting FX pair profiles (`FXClient(from_currency, to_currency).profile()`),
  returning from/to currency, exchange, region, description, last updated,
  source, day open/high/low/close/average, year open/high/low/close/average
  (trailing 52-week window, `year_open` from a `history(period="1y")` call,
  `*_average` as the high/low midpoint), and the 50-/200-day moving averages.
  Configured via `packages/fx/config/fx_pairs.yaml` (GBP/USD, USD/GBP,
  GBP/EUR, EUR/GBP by default); its CLI writes one Parquet file per pair to
  `fx=<PAIR>/profile.parquet`, reading pairs from that config or a
  `--pairs-json` string, with `--max-workers`/`--max-calls`/`--period-seconds`
  to control concurrency and the shared rate limit.
- `equicast-fx-plan`: a second CLI entry point that splits the configured FX
  pairs into chunks (capped at 256 — GitHub's per-workflow matrix job limit),
  growing the chunk size rather than dropping pairs if needed.
- `packages/fx/Dockerfile`, built and pushed to GHCR as a private image via
  the new `fx-image.yml` workflow.
- `fx-ingestion.yml`: runs every 6 hours (and on demand) as two jobs — a
  `plan` job computing chunks via `equicast-fx-plan`, and an `ingest` matrix
  job (one leg per chunk, `max-parallel: 20`) that pulls the `equicast-fx`
  image, passes its chunk via `--pairs-json`, and uploads the resulting
  Parquet files to `s3://equicast-market-data-<env>/fx=<PAIR>/`. Scales to
  large pair lists both across legs (separate runners/IPs) and within each
  container (concurrent fetches under a shared rate limit).
- `fx-ci.yml`: ruff, mypy, and pytest for `equicast-datafeed` and
  `equicast-fx`.
- `FXClient.prices(full_load=False)`: returns one daily OHLC record per
  trading day (from/to currency, date, open, high, low, close, average,
  last updated, source). Defaults to the current year (`period="ytd"`);
  `full_load=True` fetches the pair's entire yfinance history instead
  (`period="max"`). The CLI writes one `fx=<PAIR>/year=<YYYY>/price.parquet`
  per year covered, and a `--full-load` flag controls the same behavior;
  `fx-ingestion.yml` exposes it as a `workflow_dispatch` boolean input.
  Profile and prices are fetched as independent concurrent tasks per pair
  (submitted to the same worker pool as `--max-workers`), sharing one
  `FXClient`/`DatafeedClient` so the configured rate limit still applies
  across both.
- `docs/local-setup.md` and `docs/fx-pipeline.md`: the technical setup and
  deployment/execution details that used to live in the README, which is now
  scoped to the functional description of what equiCast produces.
- `packages/fx/scripts/smoke_test.py`: a manual QA tool (not part of the
  `pytest` suite) that runs `FXClient.profile()`/`.prices()` against live
  Yahoo Finance data for a set of pairs (defaults to `config/fx_pairs.yaml`,
  or `--pairs FROM:TO,...`), printing JSON to stdout or writing real Parquet
  via `--format parquet --out <dir>`, with `--full-load` for prices. Works
  the same way inside the Docker image via an entrypoint override;
  documented in `docs/fx-pipeline.md`.
- `equicast-metrics` (`packages/metrics/`): standalone, generic package for
  risk/performance metrics on any yfinance symbol — an FX pair (`GBPUSD=X`)
  or a stock ticker (`AAPL`) alike. `MetricsClient(symbol).metrics()` returns
  `volatility`, `sharpe_ratio`, `max_drawdown` (all trailing 1-year, Sharpe
  assuming a 0% risk-free rate), `cagr_1y`/`2y`/`3y`/`5y`/`10y` (`None` where
  there isn't enough history), `last_updated`, and `source`. Checks yfinance
  first per field (only `cagr_1y` has an equivalent, `fiftyTwoWeekChangePercent`)
  before calculating; guards against a still-forming trading day's `NaN`
  close price poisoning every downstream calculation.
- `equicast-fx` now also writes `fx=<PAIR>/metrics.parquet` per pair (from/to
  currency plus the `equicast-metrics` fields above), fetched as a third
  concurrent task alongside profile and prices. Unaffected by `--full-load`
  (metrics always looks back as far as `cagr_10y` needs, regardless).
- `fx-ci.yml` and `.pre-commit-config.yaml` now also lint/type-check/test
  `equicast-metrics`; `packages/fx/Dockerfile` copies it into the image.
- `equicast_datafeed.round_value`/`DECIMAL_PRECISION` (8): a shared
  decimal-precision policy for every numeric field `equicast-fx` and
  `equicast-metrics` compute or re-emit, cutting off float64 representation
  noise (e.g. `1.3504753112792969` → `1.35047531`) while staying above FX's
  ~5-decimal pipette precision and the ~4-6 decimals meaningful for
  risk/performance ratios. Applied at the point each value is computed
  (`FXClient.profile()`/`.prices()`, the `equicast_metrics.calculations`
  functions, `MetricsClient.metrics()`'s yfinance-sourced `cagr_1y`) rather
  than only at JSON/Parquet output time, so every consumer sees the same
  rounded value.
- `docs/aws-github-oidc-setup.md`: reference doc for how GitHub Actions
  authenticates to AWS — the OIDC federation `terraform.yml`, `deploy.yml`,
  and `fx-ingestion.yml` all use to assume a single IAM role — covering
  manual setup (the trust policy, a least-privilege permissions policy),
  verification, and common errors (trust policy mismatches, a duplicate
  OIDC provider in the account, missing `id-token` permissions).
- Infracost cost estimation: a new `infracost` job in `terraform.yml` posts
  (and updates) one PR comment with the estimated cost diff for both the
  `dev` and `prod` projects declared in the new `infracost.yml`, using new
  `infra/infracost-usage.yml` for rough S3/ECR usage estimates (storage,
  request volume) Infracost otherwise assumes are zero. It's a pure HCL
  diff — no `terraform plan`, state, or AWS credentials involved.
  `deploy.yml`'s `estimate-backend`/`estimate-frontend` jobs separately
  print a rough, size-based cost estimate (hardcoded, approximate AWS unit
  prices) for the image/bundle about to be pushed to the run's step summary,
  visible before either gate is approved.
- `infra/modules/ecr`: added an `aws_ecr_lifecycle_policy` capping
  `equicast-backend` at the 2 most recently pushed images.
- `equicast-stock` (`packages/stock/`): standalone package, mirroring
  `equicast-fx`'s design, for extracting stock ticker profiles
  (`StockClient(ticker).profile()`), returning ticker, name, quote type,
  exchange, currency, description, sector, industry, website, beta, payout
  ratio, dividend rate/yield, market cap, volume, day
  open/high/low/close/average, year open/high/low/close/average, 50-/200-day
  moving averages, address, country, region, full-time employees, CEO(s),
  IPO date, last updated, and source. The day/year/moving-average fields
  mirror `equicast-fx`'s `FXClient.profile()` exactly (same yfinance source
  fields, same midpoint/rounding logic, same trailing-52-week `year_*`
  window via a `history(period="1y")` call).
  `address` is formatted from `address1`/`address2`/`city`/`state`/`zip`,
  kept independent of the separate `country`/`region` fields (yfinance's own
  keys, not parsed out of the address string) so all three stay filterable.
  `ceos` is a list of `{"name", "role"}` entries, best-effort and tried in
  order: `companyOfficers` and `executiveTeam` (both structured — `role` is
  that person's actual title, e.g. "Chairman, President and CEO"), then a
  free-text pattern match against `longBusinessSummary` (`role` is always
  the literal string `"CEO"` there, since prose gives no real title) —
  yfinance has no dedicated CEO field. In the written Parquet file (not in
  `profile()`'s return value), `ceos` is JSON-encoded to a plain string
  column rather than a native list<struct> column — pandas/pyarrow
  round-trip the struct type fine, but common JS-based Parquet viewers just
  call `toString()` on nested objects and render `[object Object]` instead
  of the actual data; a JSON string reads correctly in any viewer.
  `ipo_date` is similarly best-effort, sourced from
  `firstTradeDateMilliseconds` (falling back to `firstTradeDateEpochUtc`) —
  yfinance has no true IPO date field either — formatted as a full ISO 8601
  datetime, same as `last_updated` (not just a date). Configured via
  `packages/stock/config/stocks.yaml` (AAPL, MSFT, GOOGL, AMZN, NVDA, META,
  TSLA, QCOM, AVGO by default); its CLI writes `stock=<TICKER>/profile.parquet`,
  reading tickers from that config or a `--tickers-json` string.
- `StockClient.prices()`: one daily OHLC record per trading day (ticker,
  currency, date, open/high/low/close/average, last updated,
  source=yfinance), mirroring `FXClient.prices()` — current year only by
  default (`ytd`), or the ticker's entire yfinance history with
  `full_load=True` (`max`). Unlike the from/to-currency pairs `equicast-fx`
  already knows, `currency` isn't available on `StockClient` itself, so
  `prices()` makes its own `get_info()` call to read it. The CLI writes one
  `price.parquet` per year covered to
  `stock=<TICKER>/year=<YYYY>/price.parquet`, alongside profile.parquet, via
  a new `--full-load` flag (same shape as `equicast-fx`'s).
- `equicast-stock-plan`: a second CLI entry point, identical in shape to
  `equicast-fx-plan`, splitting the configured tickers into chunks (capped
  at 256) for the ingestion workflow's matrix.
- `packages/stock/Dockerfile`, built and pushed to GHCR as a private image
  via the new `stock-image.yml` workflow.
- `packages/stock/scripts/smoke_test.py`, mirroring `equicast-fx`'s: a
  manual QA tool (not part of the automated `pytest` suite) exercising
  `StockClient.profile()`/`.prices()`, `DividendsClient.dividends()`,
  `MetricsClient.metrics()`/`.fundamentals()`, and the Parquet writers
  against live Yahoo Finance data, with `--tickers`, `--format json|parquet`,
  and `--full-load` options.
- `stock-ingestion.yml`: runs every 6 hours (and on demand) as two jobs,
  structured identically to `fx-ingestion.yml` — a `plan` job computing
  chunks via `equicast-stock-plan` and resolving the target
  environment/bucket, and an `ingest` matrix job uploading the resulting
  profile/price/dividend/metrics Parquet files to
  `s3://equicast-market-data-<env>/stock=<TICKER>/`, with a `full_load`
  input controlling prices'/dividends' history depth (same shape as
  `fx-ingestion.yml`'s). Shares the bucket and the
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variables with
  `fx-ingestion.yml`. Scheduled at `0 2,8,14,20 * * *` — offset 2 hours from
  FX's `0 */6 * * *` — so the two pipelines never overlap even if a run
  takes longer than expected.
- `stock-ci.yml`: lint/type-check/test for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, and `equicast-stock`, mirroring
  `fx-ci.yml`.
- `docs/stock-pipeline.md`, documenting the stock pipeline's architecture,
  local/Docker usage, and scheduled-run inputs (mirrors
  `docs/fx-pipeline.md`).
- `equicast_datafeed.DatafeedClient.get_balance_sheet()`/`.get_financials()`:
  fetch a ticker's annual balance sheet/income statement (`yf.Ticker(...).balance_sheet`/
  `.financials`), through the same rate-limit/retry wrapper as
  `get_info()`/`get_history()`.
- `MetricsClient.fundamentals()` (`equicast-metrics`): stock-only
  valuation/fundamental metrics — trailing/forward PE, trailing/forward EPS,
  PEG, price-to-book, price-to-sales, EV/EBITDA, gross/operating/profit
  margin, return on equity/assets, debt-to-equity, and free cash flow per
  share. For each field, prefers yfinance's `.info` directly, then a ratio
  built from other `.info` fields, and only as a last resort a line item
  pulled from the new `get_balance_sheet()`/`get_financials()` calls
  (fetched lazily, at most once each, since most tickers resolve every field
  from `.info` alone). PEG falls back to `trailing_pe / (earningsGrowth * 100)`
  when yfinance doesn't report `trailingPegRatio`/`pegRatio`. Raises the new
  `equicast_metrics.UnsupportedSymbolError` for an FX symbol (one ending in
  `"=X"`) — FX pairs have no earnings or balance sheet, so this is
  `equicast-stock`-only; `equicast-fx` never calls it.
- `equicast-stock`'s CLI now also computes metrics: a new `_metrics_task`
  calls both `MetricsClient.metrics()` and `.fundamentals()` and merges them
  into one `stock=<TICKER>/metrics.parquet` row (via a new
  `write_metrics_parquet`), reconciling the two independently-computed
  `last_updated`/`source` pairs into one of each. `equicast-metrics` is now
  a dependency of `equicast-stock` (`pyproject.toml`, `Dockerfile`,
  `stock-image.yml`'s path filters).
- `equicast_datafeed.DatafeedClient.get_dividends()`: fetches a symbol's
  historical dividends (`yf.Ticker(...).dividends`, ex-dividend date to cash
  amount per share) through the same rate-limit/retry wrapper as the other
  `get_*` methods.
- `equicast-dividends` (`packages/dividends/`): a new standalone package,
  generic across any yfinance equity-like symbol the same way
  `equicast-metrics`' `MetricsClient` is (not `equicast-stock`-specific, so
  a future ETF package can reuse it). `DividendsClient(symbol).dividends()`
  returns one record per ex-dividend date —
  `{ticker, currency, ex_dividend_date, price, last_updated, source}` —
  `price` being the dividend cash amount per share, not a stock price.
  Defaults to the current calendar year only (client-side filtering, since
  yfinance's dividends call has no period parameter of its own — the full
  series is always fetched in one call); `dividends(full_load=True)` returns
  every year instead. Deliberately has no `payment_date` field: yfinance's
  dividend history (scraped from Yahoo's dividend table) only ever has
  ex-dividend date and amount, for any ticker, at any point in history.
  Constructing a `DividendsClient` shows its own `EQUICAST_DIVIDENDS_DISCLAIMER`
  (distinct text from `equicast-datafeed`'s `YFINANCE_DATA_DISCLAIMER`, unlike
  `FXClient`/`StockClient` which reuse it) so it's always visible on its own,
  the same way `equicast-metrics`' disclaimer is, rather than silently
  deduped away when `DatafeedClient`'s disclaimer already fired earlier in
  the same process.
- Wired `equicast-dividends` into `equicast-stock`: a new `_dividends_task`
  in the CLI writes `stock=<TICKER>/year=<YYYY>/dividend.parquet` per year
  covered (via a new `write_dividend_parquet`), reusing the same
  `--full-load` flag as prices. `equicast-dividends` is now a dependency of
  `equicast-stock` (`pyproject.toml`, `Dockerfile`, `stock-image.yml`'s path
  filters) and of the root workspace (`pyproject.toml`), with its own
  `mypy`/`pytest` hooks added to `.pre-commit-config.yaml` and
  `docs/local-setup.md` gaining the stock packages' setup instructions it
  was previously missing.
- `equicast-etf` (`packages/etf/`): new standalone package, mirroring
  `equicast-stock`'s design (same starting point `equicast-stock` itself
  had). `ETFClient(ticker).profile()` returns ticker, name, quote type,
  exchange, currency, description, category, fund family, website, beta,
  expense ratio, dividend rate/yield, total assets, NAV price, volume,
  day/year price range and moving averages, YTD/3yr/5yr average returns,
  inception date, last updated, and source. Several `equicast-stock`
  profile fields don't apply to a fund and
  are dropped (`sector`/`industry`, `market_cap`, `payout_ratio`, `ceos`,
  `address`/`country`/`region`/`full_time_employees`) or re-sourced from a
  different yfinance field under the same name (`beta` here comes from
  yfinance's `beta3Year`, not a plain `beta` — yfinance has none for ETFs;
  `ipo_date` becomes `inception_date`, sourced from yfinance's
  `fundInceptionDate` instead of `firstTradeDateMilliseconds`/
  `firstTradeDateEpochUtc`, though those remain the fallback if
  `fundInceptionDate` is missing). `website` is the one field not sourced
  from yfinance at all — yfinance never populates it for ETFs (confirmed
  empty across Vanguard/iShares/Invesco/State Street/Schwab/BlackRock-issued
  funds) — so it's looked up from a small static `fund_family` →
  issuer-website map instead, matched by substring since `fundFamily` itself
  varies by ticker for the same issuer. Configured via
  `packages/etf/config/etfs.yaml` (VOO, QQQ, VTI, AGG, GLD by default —
  diversified across categories/issuers rather than picked for any other
  reason); its CLI writes `etf=<TICKER>/profile.parquet`, reading tickers
  from that config or a `--tickers-json` string.
- `ETFClient.prices()`: one daily OHLC record per trading day (ticker,
  currency, date, open/high/low/close/average, last updated,
  source=yfinance), mirroring `StockClient.prices()`/`FXClient.prices()` —
  current year only by default (`ytd`), or the ticker's entire yfinance
  history with `full_load=True` (`max`). `currency` isn't already known by
  `ETFClient`, so `prices()` makes its own `get_info()` call to read it. The
  CLI writes one `price.parquet` per year covered to
  `etf=<TICKER>/year=<YYYY>/price.parquet`, alongside profile.parquet, via a
  new `--full-load` flag (same shape as `equicast-stock`'s).
- Wired `equicast-dividends` into `equicast-etf`: a new `_dividends_task` in
  the CLI writes `etf=<TICKER>/year=<YYYY>/dividend.parquet` per year
  covered (via a new `write_dividend_parquet`), reusing the same
  `--full-load` flag as prices. `DividendsClient` is the same generic,
  symbol-keyed client `equicast-stock` already consumes — not duplicated
  for ETFs — so `equicast-etf` gets dividend history with no new
  dividend-fetching logic of its own. `equicast-dividends` is now a
  dependency of `equicast-etf` (`pyproject.toml`, `Dockerfile`,
  `etf-ci.yml`'s/`etf-image.yml`'s path filters).
- Wired `equicast-metrics` into `equicast-etf`: a new `_metrics_task` in the
  CLI writes `etf=<TICKER>/metrics.parquet` (via a new
  `write_metrics_parquet`, ticker-keyed the same way `equicast-stock`'s is).
  Only calls `MetricsClient.metrics()` (volatility, Sharpe ratio, max
  drawdown, CAGR 1/2/3/5/10y) — deliberately **not** `.fundamentals()`,
  unlike `equicast-stock`: checked live against VOO/QQQ/AGG/GLD first, and
  12-13 of its 15 valuation fields came back `None` for every one of them,
  with the couple that didn't (`trailing_pe`, `price_to_book`) being an
  inconsistent yfinance aggregate-portfolio figure rather than a genuine
  fund fundamental. The fund-level figures that matter for an ETF (expense
  ratio, NAV, AUM, category, YTD/3yr/5yr returns) already live in
  `profile()`, so there was no gap for a `fundamentals()`-style tier to
  fill. `equicast-metrics` is now a dependency of `equicast-etf`
  (`pyproject.toml`, `Dockerfile`, `etf-ci.yml`'s/`etf-image.yml`'s path
  filters).
- Wired `equicast-events` into `equicast-etf`: a new `_events_task` in the
  CLI writes `etf=<TICKER>/year=<YYYY>/events.parquet` per year covered
  (via a new `write_events_parquet`, using the same pinned pyarrow
  `_EVENTS_SCHEMA` as `equicast-stock`'s — kept as its own copy since
  `equicast_stock` isn't a dependency of `equicast_etf`), reusing the same
  `--full-load` flag as prices/dividends. `EventsClient` is the same
  generic, symbol-keyed client `equicast-stock` already consumes. Checked
  live for all 5 configured tickers first: `earnings`/`rating` event types
  are always empty for an ETF (no earnings reports or analyst coverage for
  a fund), so `events.parquet` in practice only ever has `"split"` rows —
  but those are real: VOO (2013), QQQ (2000, 2-for-1), and VTI (2008,
  2-for-1) each have exactly one in their full yfinance history; AGG and
  GLD have none. `equicast-events` is now a dependency of `equicast-etf`
  (`pyproject.toml`, `Dockerfile`, `etf-ci.yml`'s/`etf-image.yml`'s path
  filters).
- `equicast-etf-plan`: a second CLI entry point, identical in shape to
  `equicast-stock-plan`, splitting the configured tickers into chunks
  (capped at 256) for the ingestion workflow's matrix.
- `packages/etf/Dockerfile`, built and pushed to GHCR as a private image via
  the new `etf-image.yml` workflow.
- `packages/etf/scripts/smoke_test.py`, mirroring `equicast-stock`'s: a
  manual QA tool (not part of the automated `pytest` suite) exercising
  `ETFClient.profile()`/`.prices()`, `DividendsClient.dividends()`,
  `EventsClient.events()`, `MetricsClient.metrics()`, and the Parquet
  writers against live Yahoo Finance data, with `--tickers`,
  `--format json|parquet`, and `--full-load` options.
- `etf-ingestion.yml`: runs every 6 hours (and on demand) as two jobs,
  structured identically to `fx-ingestion.yml`/`stock-ingestion.yml` — a
  `plan` job computing chunks via `equicast-etf-plan` and resolving the
  target environment/bucket, and an `ingest` matrix job uploading the
  resulting profile/price/dividend/events/metrics Parquet files to
  `s3://equicast-market-data-<env>/etf=<TICKER>/`, with a `full_load` input
  controlling prices'/dividends'/events' history depth (same shape as
  `fx-ingestion.yml`'s/`stock-ingestion.yml`'s). Shares the bucket and the
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variables with
  `fx-ingestion.yml`/`stock-ingestion.yml`. Scheduled at `0 4,10,16,22 * * *`
  — offset 4 hours from FX's `0 */6 * * *` and 2 hours from stock's
  `0 2,8,14,20 * * *` — so none of the three pipelines overlap even if a run
  takes longer than expected.
- `etf-ci.yml`: lint/type-check/test for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, `equicast-events`, and
  `equicast-etf`, mirroring `stock-ci.yml`.
- `docs/etf-pipeline.md`, documenting the ETF pipeline's architecture,
  local/Docker usage, and scheduled-run inputs (mirrors
  `docs/stock-pipeline.md`).
- Added an ETF section to `infra/infracost-usage.yml`'s
  `module.market_data_bucket.aws_s3_bucket.this` estimate, sized from real
  per-file measurements (profile.parquet ~22-23KB, rounded to 25KB/ticker;
  price.parquet ~14KB for a partial year, scaling to ~20KB/year — the same
  figure the Stock section uses; dividend.parquet ~4KB for a partial year
  across VOO/QQQ/VTI/AGG — GLD pays none — scaling to ~5KB/year, smaller
  than the Stock section's assumed 10KB/year since ETF distributions here
  carry no other per-row fields; events.parquet ~7.2KB per file that
  actually exists — modeled as up to 1 accumulated file per ticker rather
  than one per year like price/dividend, since splits are rare (3 of 5
  configured tickers have exactly one split ever, not one per year);
  metrics.parquet ~6.7KB, identical across tickers since the schema is
  fixed, notably smaller than the Stock
  section's 20KB since it's risk/performance only, no fundamentals) rather
  than a placeholder, following the same real-sample approach the Stock
  section was re-sized to use.

### Changed

- Re-sized `infra/infracost-usage.yml`'s Stock section from real per-file
  estimates instead of placeholders: profile.parquet ~30KB and
  metrics.parquet ~20KB (one-time snapshots), plus price.parquet ~20KB/year,
  dividend.parquet ~10KB/year, and events.parquet ~10KB/year — the latter
  three now projected across 20 years of accumulated `year=<YYYY>`
  partitions per ticker (~850KB/ticker total) rather than only the current
  year, and now including `events.parquet` in both the size and PUT-request
  counts. `packages/stock/config/stocks.yaml`'s cost-estimate comment
  updated to match.
- Restructured the repo: `equicast`, `equicast-datafeed`, and `equicast-fx`
  now live under `packages/<name>/` (each its own independent distribution,
  own `pyproject.toml`, own `src/` layout). The root `pyproject.toml` became a
  virtual uv workspace root (`[tool.uv.workspace]` only, no `[project]` of its
  own) listing `packages/equicast`, `packages/datafeed`, `packages/fx`, and
  `backend` as members, sharing one lockfile/`.venv` for local dev and CI.
- Replaced the Terraform-managed, FX-scoped GitHub OIDC IAM role with a
  single, manually-created role used by all three AWS-touching workflows
  (`terraform.yml`, `deploy.yml`, `fx-ingestion.yml`), referenced by one
  repo secret, `AWS_ROLE_ARN`. Removes the circularity of Terraform needing
  AWS credentials to create the very OIDC setup meant to replace long-lived
  credentials — the provider and role are now bootstrapped once, manually,
  outside Terraform's management. `deploy.yml` and `terraform.yml` also
  moved off static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secrets onto
  this same role. Removed `infra/modules/github_oidc_role/` and the
  `fx_ingestion_role_arn` Terraform output entirely; documented the manual
  setup in `docs/aws-github-oidc-setup.md`.
- Default AWS region changed from `us-east-1` to `eu-west-1` across
  Terraform (`aws_region` variable, `terraform.tfvars.example`, the
  commented remote-state backend example) and every workflow's
  `AWS_REGION` fallback.
- Consolidated the GitHub Actions IAM role from
  `equicast-github-actions-prod-role` to a single `equicast-github-actions`,
  shared by dev and prod (matching what `docs/aws-github-oidc-setup.md`
  already documented); the `AWS_ROLE_ARN` repo secret was updated to match.
- `infra/backend.tf`: enabled the S3 remote state backend
  (`equicast-tf-state`, using Terraform's native S3 state locking —
  `use_lockfile`, no DynamoDB table needed), previously left fully commented
  out — every `terraform apply` in CI had been silently using a throwaway
  local backend on the ephemeral runner, so Terraform had no memory of
  previously-created resources between runs. State is split per environment
  via `-backend-config="key=..."` at `terraform init` time
  (`equicast/dev/terraform.tfstate`, `equicast/prod/terraform.tfstate`),
  since a backend block's `key` can't be interpolated with
  `var.environment`. `infra/providers.tf`'s `required_version` bumped to
  `>= 1.10` for native locking support. Documented in new
  `docs/terraform-state-setup.md`, including the bucket bootstrap steps and
  the `terraform import` runbook for resources created by earlier `apply`
  runs before the backend existed.
- Dev/prod environment split, gated behind explicit approval: `terraform.yml`'s
  `apply` job is now `apply-dev` (runs automatically on push to `main`,
  `-var environment=dev`) followed by `apply-prod` (`-var environment=prod`,
  gated behind the `production` GitHub Environment's required reviewers).
  `deploy.yml` similarly splits backend/frontend each into an `estimate-*`
  job (builds the image/bundle once) plus `deploy-*-dev` (gated behind a new
  `deploy-dev` environment) and `deploy-*-prod` (gated behind `production`),
  promoting the exact artifact `estimate-*` built rather than rebuilding.
- Disabled S3 bucket versioning on `market_data_bucket` (cost reasons); it
  now uses the `s3_bucket` module's default (`false`), same as
  `frontend_bucket` already did.
- Fixed `deploy-backend-prod`'s image promotion: `equicast-backend` is
  `IMMUTABLE`, so re-pointing the `prod` tag on a second promotion would
  have failed (`ImageAlreadyExistsException`) — it now deletes the existing
  `prod` tag first (a no-op the first time).
- Paused deploying the frontend/backend, since there's nothing ready to
  ship yet and keeping the S3 bucket/ECR repo around just to sit empty
  costs money for nothing: `infra/main.tf`'s `frontend_bucket`/`backend_ecr`
  modules and their outputs in `infra/outputs.tf` are commented out (not
  deleted), and `deploy.yml`'s backend/frontend jobs are likewise commented
  out and replaced by a no-op `paused` job so the workflow stays valid and
  green. `market_data_bucket` and `fx-ingestion.yml` are unaffected.
- Fixed `fx-ingestion.yml` uploading to `s3:///fx=<PAIR>/...` (empty bucket
  name, `aws s3 cp` rejecting it with `Invalid bucket name ""`): the
  `MARKET_DATA_BUCKET` variable it read had never been set anywhere. Added
  a `workflow_dispatch` `environment` input (`dev`/`production`, default
  `dev`) and a `plan`-job step that resolves the target environment —
  the scheduled trigger always resolves to `production` (there's no input
  to read on a cron run), manual runs use the input — and looks up the
  matching bucket from two new plain repo variables,
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` (not scoped to the
  `dev`/`production` GitHub Environments, since `production`'s
  required-reviewer rule would otherwise pause every scheduled run pending
  approval). Fails fast with a clear `::error::` if the relevant variable
  is unset, rather than surfacing the confusing empty-bucket AWS error.
  Documented in `docs/fx-pipeline.md`.
- Sized `infra/infracost-usage.yml`'s `market_data_bucket` estimate from
  per-file Parquet sizes instead of a flat guess: `storage_gb` (`20` →
  `0.01`) and `monthly_tier_1_requests` (`5000` → `1500`) are now computed
  from profile.parquet (~15KB), metrics.parquet (~10KB), and price.parquet
  (~20KB/year) against the pair count in
  `packages/fx/config/fx_pairs.yaml` (currently 4) and `fx-ingestion.yml`'s
  6-hourly schedule — see that file's comments for the formula.
  `packages/fx/config/fx_pairs.yaml` now points back at it, so the cost
  estimate isn't forgotten the next time the pair list changes.
- Extended the same `market_data_bucket` estimate with a Stock section,
  broken out and summed alongside FX's: profile.parquet (~45KB/ticker
  placeholder) + price.parquet (~20KB/year) + the new metrics.parquet
  (~15KB/ticker placeholder) against `packages/stock/config/stocks.yaml`'s
  9 tickers and `stock-ingestion.yml`'s 6-hourly (offset) schedule —
  `monthly_tier_1_requests` (`3700` → `4800`) now covers both pipelines'
  three files/run each. `packages/stock/config/stocks.yaml` now points back
  at it too.
- Extended the Stock section again for the new dividend.parquet (~2KB/ticker
  placeholder — just a handful of rows per year, often none at all):
  `storage_gb` stays `0.01` (still well under 1GB) but
  `monthly_tier_1_requests` (`4800` → `5900`) now covers four files/run
  (profile + price + dividend + metrics) instead of three.
