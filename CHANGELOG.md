# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- All five system-default watchlists (Global Markets, Top Winners, Top
  Losers, Your Top Winners, Your Top Losers) are now live, computed at
  request time by `backend/watchlists/system_watchlists.py` from what
  fx/stock/etf/benchmark/future-ingestion.yml already publish — no
  separate ingestion pipeline builds or schedules them. `equicast_metrics.
  MetricsClient.metrics()` gained `change_1w_pct`/`change_1m_pct`
  (alongside the `cagr_1y` it already computed), shared by all five
  pipelines for free; `equicast_core.catalog.build_catalog_rows` folds all
  three into each asset class's `catalog/<asset_class>.parquet` from that
  ticker's sibling `metrics.parquet` (each ingestion workflow's `ingest`
  job now bundles `metrics.parquet` into the same artifact `build-catalog`
  already downloads, so this adds zero S3 reads anywhere, build time or
  request time — the backend needs at most one `get_catalog` read per
  asset class per system watchlist). Global Markets looks up a
  hand-curated 24-ticker list (`GLOBAL_MARKETS_ENTRIES`) across the fx/
  future/benchmark catalogs; Top Winners/Top Losers rank the whole stock/
  ETF universe by `cagr_1y`, positive/negative only, capped at
  `MAX_HOLDINGS_FOR_WATCHLIST` (default 50); Your Top Winners/Your Top
  Losers apply that same ranking to just the caller's own account/pie
  holdings (deduplicated by ticker — plain watchlist holdings never
  count, they were never "held"), enriched the same way a custom
  watchlist's holdings are. `WatchlistEntryCard` renders a third "1Y"
  stat (`change_1y_pct`, the ranking CAGR as a percent) whenever it's
  present. Retires the `equicast-watchlist` package
  (`packages/watchlist`) and its `watchlist-ingestion.yml`/
  `watchlist-image.yml`/`watchlist-ci.yml` workflows entirely — the
  weekly-batch, fetch-fresh-from-yfinance design they replaced never
  reused any other pipeline's published data; this one reuses all of it.

- A fifth ingestion pipeline, `equicast-future` (`packages/future`), for
  futures contracts (Gold, Silver, Platinum, Palladium, WTI/Brent Crude,
  Natural Gas, Heating Oil, Copper, Aluminum, Wheat, Corn, Soybeans,
  Coffee, Cotton, Sugar — 16 total, same list in both dev and prod
  configs) — mirrors `equicast-benchmark` exactly (a future is a single
  yfinance symbol, no dividends/fundamentals), landing as `future=<KEY>/
  {profile,metrics,price}.parquet` in the shared market-data bucket and a
  `catalog/future.parquet` search catalog. `future-ingestion.yml` runs
  once daily on weekdays at 23:15 UTC, 15 minutes after
  `benchmark-ingestion.yml` (`fx > etf > stock > benchmark > future`, none
  ever overlap), with the same `--tickers` targeted-run support and
  per-task failure isolation (equicast-support#145) every other pipeline
  already has, and its CI/image build are folded into the shared
  `packages-ci.yml`/`images.yml` matrices rather than standalone
  workflows. Like a benchmark, a future isn't directly holdable in a
  pie/account/watchlist — `equicast_core.client.ASSET_CLASSES` gained
  `"future"` as an opt-in-only search class (not part of
  `DEFAULT_SEARCH_ASSET_CLASSES`), and `equicast_core.catalog`'s
  `--asset-class` choices gained it too; no change to
  `backend/holdings/views.py`'s own (narrower) holdable-asset-class set.

- `/search`'s Type filter gained a "Futures" option (`SearchFilters.jsx`),
  alongside Stocks/ETFs/FX/Benchmark Index — a future is now something a
  user can search for directly, the same way Benchmark Index already was.
  No backend change needed — `SearchView`/`MarketDataClient.search`
  already accepted an explicit `asset_class=future` from the futures
  pipeline work above; this just exposes it in the UI. `AssetTypeBadge`
  gained a "Futures" label/tone for a future search result's row badge.
  Market cap/Sector/Industry still silently exclude every future row when
  applied (it has none of those concepts, same as a benchmark) — only
  Exchange meaningfully narrows one.

- A watchlists panel on `/dashboard` (`WatchlistsPanel`, below the accounts
  grid), tabbed across five system-default watchlists (Global Markets, Top
  Winners, Top Losers, Top Winners/Losers within your accounts — always
  present, always first, holdings empty for now; how each actually gets
  populated is deliberately separate, not-yet-built work) followed by the
  caller's own custom watchlists. Custom watchlists reuse the
  already-existing `WatchlistsClient`/`backend/watchlists` CRUD (capped at
  `MAX_WATCHLISTS`, 5) — `GET /api/watchlists/` now returns one merged list
  (system + custom, each tagged `type`), with every custom watchlist's
  holdings nested and enriched the same way `PieListView.get` nests a pie's.
  Adding/removing a custom watchlist's holdings goes through the existing
  `POST`/`DELETE /api/holdings/` with `watchlist_id` (already supported
  server-side, just not previously used from the frontend) rather than any
  new endpoint. New generic `Tabs` component (`components/core/Tabs.jsx`).
  Per-watchlist holding caps (`MAX_HOLDINGS_FOR_WATCHLIST`, already a
  GitHub Environment variable wired into terraform) aren't yet set to
  different dev/prod values — that's a config change, not code.

### Fixed

- Fixed news dates showing as the ingestion run date instead of each
  article's real publish date, caused by fetching yfinance's live
  "latest" news feed instead of its full archive (equicast-support#231).
- Fixed the "Something went wrong" error page showing the signed-in
  Topbar (ticker search, account menu) to signed-out visitors, caused by
  it always rendering the signed-in chrome regardless of auth state.
- Fixed exchange rate warm-up on login firing one request per currency pair
  at once, which could hit the same rate limit as the account/pie price
  charts for users with several currencies configured.
- Fixed a CI warning on the packages workflow caused by parallel jobs
  racing to save the same dependency cache.

## [1.1.5] - 2026-09-24

### Fixed

- Fixed account/pie price charts failing to load for portfolios with many
  holdings, caused by too many simultaneous price requests hitting the
  rate limit.

## [1.1.4] - 2026-09-24

### Fixed

- Fixed ticker search returning no results for any query, caused by the
  nightly market data ingestion silently publishing an empty search index.

## [1.1.3] - 2026-09-24

### Fixed

- Fixed a crash on the landing page's demo price chart when a ticker's
  price history had a missing price, which took down the whole page.

## [1.1.2] - 2026-09-24

### Fixed

- Fixed ingestion pipeline-failure tracking issues sometimes failing to sync correctly.

## [1.1.1] - 2026-09-24

### Fixed

- Fixed price history endpoints erroring for tickers with a day missing a high/low price.

## [1.1.0] - 2026-09-23

### Added

- Accounts can now optionally record a vendor/platform (e.g. Trading212, Chip), shown as a tag (equicast-support#171).
- Ingestion pipeline failures are now reported automatically as tracking issues instead of only showing up in CI.
- Docker images are now tagged with an auto-incrementing version, with old versions pruned automatically.
- Destroying or redeploying infrastructure now keeps Auth0's login redirect URLs in sync automatically.
- Stock and ETF ingestion now flags holdings whose currency can't be converted, opening a support issue per missing FX pair (equicast-support#164).
- Added a UK dividend tax calculation engine that applies allowances and tax bands automatically (GitHub issue #212).
- Added a Dividend Allowance page showing this and prior UK tax years' allowance usage and tax deducted.

### Changed

- The import wizard's Source picker now shows an icon per preset instead of a plain text dropdown (equicast-support#146).
- An account's Portfolios and Holdings lists are now sorted by current value, highest first (equicast-support#193).
- A pie's Holdings list is now sorted by current value, highest first (equicast-support#194).
- Ingestion workflows now run with more concurrency, spread more evenly across parallel runners (equicast-support#168).
- Ingestion now caches repeated market-data fetches within a run instead of re-fetching them (equicast-support#168).
- Ingestion workflows now clean up their intermediate artifacts once finished.
- CI, Docker builds, Terraform, and deploy now also run on release-integration branches, same as main.
- Docker image builds now only rebuild the images actually affected by a push.
- Per-package CI workflows now test each shared package once instead of once per asset class.
- Ingestion pipeline-status reporting, artifact cleanup, Terraform apply, frontend build, and AWS credential setup steps are now shared actions instead of duplicated per workflow.
- GitHub Actions used across CI/CD are updated to their latest major versions.
- An account's/pie's Sector and Industry diversification charts are now combined into one with drill-down (equicast-support#192).
- The "New account"/"Edit account" drawer now asks for vendor before icon.
- An account card's vendor tag now sits alongside its pies/holdings counts.
- Adding a transaction now locks the whole form, not just the buttons, while it saves.
- The import review screen now has Select all/Unselect all buttons and no longer requires reselecting the target account for a brand-new account.
- The home page now highlights UK dividend tax & allowance tracking as an available feature (equicast-support#203).
- The home page's hero now shows more of equiCast's implemented concepts as floating chips (equicast-support#203).
- The home page no longer describes equiCast's data as "live", since prices refresh once a day (equicast-support#203).
- The home page's demo chart now opens in line view by default instead of candles (equicast-support#203).
- The home page's "Available today" section is now a spotlight list for its top features with a compact strip for the rest (equicast-support#203).

### Fixed

- A ticker page's News panel now shows however many cards actually fit per row instead of a fixed 4 (equicast-support#177).
- An account's or pie's page no longer shows the price chart when none of its holdings have shares yet (equicast-support#172).
- The Holdings heatmap no longer draws a tile per holding when none of them actually have shares (equicast-support#175).
- Fixed holding icons misaligning rows when a holding has no website (equicast-support#178).
- The UK dividend tax allowance is no longer permanently "used" when a dividend that had consumed some of it is edited, deleted, or dropped (equicast-support#1).
- Adding a holding now closes the drawer automatically once it's added.
- Fixed a crash computing UK dividend tax for a second taxable dividend in the same tax year.
- Deleting a holding, account, or pie with taxed dividends no longer leaves the UK dividend allowance permanently "used".
- The Holdings heatmap and diversification charts no longer render when none of the holdings actually have shares.
- Industry percentages in the Sector diversification drill-down now correctly sum to 100% for the selected sector.
- Truncated sector/industry names now show their full name as a tooltip on hover.

## [1.0.9] - 2026-09-22

### Added

- Ticker-request support tickets can now be resolved by replying with the config change — the entry is added/updated/deleted in the ingestion config and a PR opened automatically (equicast-support#6).

### Changed

- Consolidated the issue-automation fix and branch-cleanup workflows into one shared workflow per concern, instead of one per scenario.

## [1.0.8] - 2026-09-21

### Added

- Missing-ISIN sub-issues can now be resolved by replying with the ISIN — the fix is applied and a PR opened automatically.
- Added WDC to the production stock ticker list.
- Documented how GitHub issue automations (like the missing-ISIN auto-fix) work and how to add new ones.

## [1.0.7] - 2026-09-20

### Added

- Added SMH.L to the production ETF ticker list.

## [1.0.6] - 2026-09-20

### Added

- Added VWRL.L and ITWN.L to the production ETF ticker list.

## [1.0.5] - 2026-09-20

### Added

- Added GDX.L and QNTG.L to the production ETF ticker list.

### Fixed

- Fixed the native price field on Add/Edit Transaction rejecting more than
  2 decimal places.

## [1.0.4] - 2026-09-20

### Added

- Ingestion workflows (stock, ETF, FX, benchmark) can now be manually run
  against specific tickers instead of the full config, so adding a new
  holding no longer requires a costly full-load run across everything.
- Added NWG.L to the production stock ticker list.

### Fixed

- Fixed the market data API returning a server error when a requested
  ticker's data file doesn't exist yet (e.g. no dividend forecast on
  record).

## [1.0.3] - 2026-09-20

### Fixed

- Fixed currency conversion for LSE holdings priced in pence sterling, which could be off by 100x or fail to display.

## [1.0.2] - 2026-09-20

### Fixed

- Fixed the per-user data storage bucket never getting created when an environment is destroyed and redeployed.

## [1.0.1] - 2026-09-20

### Fixed

- Fixed the market data API returning server errors on every request in
  production (surfaced in the browser as a CORS failure on the demo prices
  endpoint).
- Fixed ETF dividend ingestion crashing on tickers with no dividend data
  available.
- Fixed stock fundamentals ingestion crashing on tickers with unexpected
  data from the market data provider.

## [1.0.0] - 2026-09-20

### Added

- Added a Support page for raising queries, requesting new tickers, or reporting incorrect data without going through GitHub (GitHub issue #246).
- Missing-ISIN tickers are now reported automatically as GitHub tracking issues (GitHub issue #215).
- Laid the groundwork for UK dividend tax: accounts now record a wrapper type, and user profiles record tax residency, income tax band, and per-holding tax domicile/withholding overrides (GitHub issue #94).
- Transactions can now optionally record UK Stamp Duty Reserve Tax and a currency-conversion fee, with the transaction entry form simplified to a single "Add" button plus a type dropdown (GitHub issues #100, #101, #201).
- The Transactions panel's "See all" list now matches the compact card layout used elsewhere, instead of a plain table (GitHub issue #181).
- Transaction imports (CSV/Trading 212) now match a row to equicast's catalog by ISIN first, falling back to ticker matching (GitHub issue #191).
- Added a footer disclaimer noting that imported figures may not exactly match a trading app or personal tracker.
- Added a cookie consent banner and a public Cookie Policy page.
- Added Google Analytics, respecting the cookie banner's Analytics consent toggle.
- Added custom error pages (404, offline, service unavailable, app crash) with animated icons, replacing silent redirects/plain error text.
- Added a public Terms and Conditions page.
- Fixed the market-data disclaimer wording, which said prices refresh "every 6 hours" when the real cadence is once a day.
- The holding price chart gained a "Key events" toggle overlaying real earnings, analyst rating, and stock split markers.
- Added a public Privacy Policy page.
- The app now shows a proper wait/retry message when a request is rate-limited, instead of a generic error.
- Added two layers of API rate limiting (a global request ceiling plus a per-user budget) to protect the backend from abuse.
- Market data reads are now cached in-memory on the backend, cutting redundant repeat lookups of the same day's data.
- Stock and ETF holdings gained a "Buy/Sell Rating" gauge on the holding detail page.
- Pies can now have a custom icon, picked from a curated set.
- Accounts can now have a custom icon, picked from a curated set.
- The holding page's benchmark comparison now shows a real 0-100 rating score against the chosen benchmark.
- The holding page's "Compare against" picker now supports comparing against real market benchmarks (S&P 500, FTSE 100, and others), not just another holding.
- Added ingestion for market benchmark/index data (S&P 500, FTSE 100, MSCI World, and more), powering the new benchmark comparisons.
- Added a dividend forecasting engine that projects a ticker's future payouts from its real historical cadence and growth rate.
- Added a helper computing a ticker's real median dividend payout gap, used to keep forecasts aligned to its actual cadence.
- Holdings now classify their dividend payout cadence (weekly/monthly/quarterly/etc.) from real historical data.
- Dividend forecasting now runs automatically on a weekly ingestion schedule.
- Search gained Sector and Industry filters.
- Rewrote the holding detail page into a full page with real price data, stats, transactions, and financials, replacing the previous shallow "held in N places" list.
- Added equicast's app icon/logo image asset.
- The topbar ticker search now shows a live preview dropdown of matches as you type, instead of navigating straight to search results.
- The holding detail page now works for any ticker, not just ones you already hold.
- Search's Market cap filter is now backed by real data, using a two-handle range slider.
- Search's Region and Exchange filters are now backed by real data, replacing their "Coming soon" placeholders.
- Search's filter panel gained a "Clear all" button and a keyword field for refining a search without returning to the topbar.
- Price, profile, and metrics data are now cached in the browser for the rest of the day, avoiding repeat API calls on revisits.
- Added an API endpoint surfacing risk, performance, and valuation metrics for a ticker, and wired it into the holding page's Stats panel.
- The holding detail page now shows a skeleton loading state instead of plain "Loading…" text.
- Added the first real domain pages: Accounts and Pies, with create/edit/delete and a shared component library.
- Added the app's design system (design tokens, light/dark theme) and its navigation shell.
- The frontend is now deployed via S3 and CloudFront instead of public static hosting.
- Added client-side routing, Auth0 sign-in, and a typed API client connecting the frontend to the backend.
- Added a local development script that runs the backend against a local AWS stand-in, for development without a real AWS account.
- Added a market search API endpoint for ticker/name lookup.
- Added a market data search catalog, letting ticker/name search work without an expensive per-ticker lookup.
- Added a Transactions domain: recording BUY/SELL/DIVIDEND transactions against a holding.
- Added a Holdings domain: holdings can now be added to an account, pie, or watchlist.
- Added a Watchlists domain: users can now create and manage watchlists.
- Added a Pies domain: pies can now be created under an account, with allocation percentages that must sum to 100%.
- Account and pie limits are now configurable per environment instead of hardcoded.
- Added an Accounts domain: users can now create and manage investment accounts.
- Added Auth0-based sign-in and per-user profile storage (default currency).
- Added ingestion for corporate events (earnings reports, analyst rating changes, stock splits).
- Added educational-use disclaimers noting that market data is sourced from Yahoo Finance and isn't financial advice.
- Initial project scaffold: core Python package for market data ingestion, on a uv workspace.
- Added a Django REST backend exposing market data.
- Added a React frontend with a minimal UI for viewing ticker history.
- Added Terraform configuration for the app's AWS infrastructure.
- Added GitHub Actions workflows for CI, Terraform, and deployment.
- Added pre-commit hooks for linting, type-checking, and unit tests.
- Added a resilient market-data client with rate limiting and retry-with-backoff, shared by every ingestion package.
- Added FX pair data ingestion (profile, price history).
- Added a chunk planner splitting configured FX pairs across parallel ingestion jobs.
- FX ingestion now runs in a Docker image published to GHCR.
- Added a scheduled FX ingestion workflow, running every 6 hours.
- Added a CI workflow for the FX ingestion packages.
- FX pairs now get full daily price history, not just a profile snapshot.
- Added local setup and FX pipeline documentation.
- Added a manual QA smoke-test script for the FX pipeline.
- Added risk/performance metrics (volatility, Sharpe ratio, max drawdown, CAGR) computable for any ticker or FX pair.
- FX ingestion now also computes and stores risk/performance metrics.
- Extended the FX CI workflow to cover the new metrics package.
- Standardized decimal rounding across every computed market-data figure.
- Added documentation for how GitHub Actions authenticates to AWS.
- Added automated cost estimates posted to infrastructure change pull requests.
- Docker images are now capped to the most recently pushed versions to limit storage cost.
- Added stock ticker data ingestion (profile: sector, financials, company info, and more).
- Stock tickers now get full daily price history, not just a profile snapshot.
- Added a chunk planner splitting configured stock tickers across parallel ingestion jobs.
- Stock ingestion now runs in a Docker image published to GHCR.
- Added a manual QA smoke-test script for the stock pipeline.
- Added a scheduled stock ingestion workflow, running every 6 hours.
- Added a CI workflow for the stock ingestion packages.
- Added stock pipeline documentation.
- Added balance sheet and income statement fetching to the shared market-data client.
- Added valuation/fundamental metrics for stocks (P/E, EPS, margins, debt-to-equity, and more).
- Stock ingestion now also computes and stores valuation/fundamental metrics.
- Added historical dividend fetching to the shared market-data client.
- Added a standalone dividend-history package, reusable across any ticker type.
- Stock ingestion now also stores dividend history.
- Added ETF ticker data ingestion (profile: expense ratio, fund family, category, and more).
- ETF tickers now get full daily price history, not just a profile snapshot.
- ETF ingestion now also stores dividend history.
- ETF ingestion now also computes and stores risk/performance metrics.
- ETF ingestion now also stores corporate events (stock splits).
- Added a chunk planner splitting configured ETF tickers across parallel ingestion jobs.
- ETF ingestion now runs in a Docker image published to GHCR.
- Added a manual QA smoke-test script for the ETF pipeline.
- Added a scheduled ETF ingestion workflow, running every 6 hours.
- Added a CI workflow for the ETF ingestion packages.
- Added ETF pipeline documentation.
- Improved the accuracy of the infrastructure cost estimate for ETF data storage.

### Changed

- Refreshed the pre-login landing page's demo chart to use real price data instead of hand-authored samples, and updated its "live today"/roadmap copy.
- Missing-ISIN tracking issues now file into the private support repo instead of the public repo.
- Account/pie price charts now plot a true since-inception value and invested-cost history, instead of an approximation of what today's holdings would have been worth historically (GitHub issue #194).
- The Buy/Sell rating gauge's bar now animates in on load instead of appearing at full width (GitHub issue #174).
- Price history requests are now bundled into one call covering every range, so the price chart no longer re-fetches on every range click (GitHub issue #150).
- Market data API responses no longer include an internal "source" field.
- Dividend history API responses no longer repeat the same ticker/currency/date fields on every entry (GitHub issue #57).
- The search catalog is now stored more efficiently on the backend, with no visible change to search itself.
- Removed now-unused table styling left over after search results became clickable.
- Tidied up how local development data files are tracked in git.
- Fixed a stock holding's CEO field always showing blank instead of the real data.
- Reduced ingestion storage-write costs by consolidating dividend history files.
- Reduced ingestion storage-write costs by consolidating corporate-events history files.
- Reduced ingestion storage-write costs by consolidating price history files.
- Ingestion now runs once daily on weekdays after markets close instead of every 6 hours, cutting infrastructure cost.
- Split infrastructure cost estimates into separate dev and prod projections reflecting their real scale.
- Tightened and reordered the ingestion pipelines' scheduling to reduce overlap.
- Ingestion pipelines now use separate ticker/pair lists for dev and prod.
- Fixed several accounts/pies issues: sign-in no longer drops on refresh, account creation and currency defaults are faster/smarter, and pages load quicker via caching.
- The local development script now sets up frontend sign-in automatically.
- CI workflows can now be triggered manually, fixing a gap where infrastructure-only changes never deployed.
- Fixed production error responses leaking debug detail, and a crash on requests missing a trailing slash.
- Newer deployments now cancel older pending ones for the same branch instead of queuing behind them.
- Simplified deployment environments from three to two, requiring approval for every dev deploy too.
- Market data endpoints now require sign-in, closing a gap where they were publicly reachable.
- Improved the accuracy of the stock data storage cost estimate.
- Restructured the repo into independent packages sharing one workspace.
- Simplified AWS access setup for GitHub Actions to a single shared role.
- Changed the default AWS region.
- Consolidated the GitHub Actions AWS role to one shared between dev and prod.
- Enabled proper remote state tracking for infrastructure changes.
- Deployments now require explicit approval before reaching dev and prod.
- Disabled unnecessary storage versioning to reduce cost.
- Fixed a repeat backend deployment failing to promote its image.
- Paused frontend/backend deployment until there was something ready to ship.
- Fixed FX ingestion failing to upload data due to a missing configuration value.
- Improved the accuracy of the FX data storage cost estimate.
- Extended the cost estimate to cover stock data storage.
- Extended the cost estimate to cover stock dividend data storage.

### Removed

- Removed the unused day/year average and moving-average price fields from market data profiles.

### Fixed

- Fixed a crash on a pie's page when removing a holding via the reallocation drawer.
- Stock and ETF profiles now include ISIN, and search can match on it.
- Added "Watchlists" and "Goals" placeholder pages to the account menu, ahead of their real UI (GitHub issue #170).
- TRANSACTION-mode holdings now backfill their dividend payout history automatically too, not just AVERAGE-mode ones (GitHub issue #124).
- AVERAGE-mode holdings now auto-record their paid dividend history instead of requiring manual entry (GitHub issue #123).
- TRANSACTION-mode holdings can now record buy/sell trades directly from the UI, not just view existing ones.
- Added recent news headlines to the holding detail page.
- Fixed the sticky header breaking on signed-out pages once you scrolled past the hero section.
- Unified the signed-out pages' headers into one shared component, fixing a misaligned logo.
- Fixed the price chart flashing blank on a time-range switch instead of updating smoothly (GitHub issue #137).
- Fixed ETF holdings being excluded from every Sector/Industry search filter.
- Fixed benchmark price comparisons getting stuck loading forever.
- Fixed the "compare against" price chart flattening one series into an unreadable line when the two series' growth rates differ by orders of magnitude.
