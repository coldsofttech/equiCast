# Release notes

User-facing summary of what shipped in each release. For the full,
implementation-level history (every change, fix, and why), see
[CHANGELOG.md](../CHANGELOG.md).

## v1.0.0 - 2026-09-20

First tagged release. Highlights:

- **Market data** — FX, stock, ETF, and benchmark ingestion pipelines
  (profiles, daily prices, dividends, corporate events, news, and
  risk/valuation metrics), sourced from Yahoo Finance and served over a
  Django REST API.
- **Accounts, pies, and holdings** — create investment accounts (ISA,
  GIA, SIPP, LISA, JISA), group holdings into pies, and track BUY/SELL/
  DIVIDEND transactions either as a running average position or a full
  trade-by-trade history.
- **Goals** — set and track financial goals against a target.
- **Importing transactions** — bring in trade history via CSV or a
  Trading 212 export, with ISIN-first matching against equicast's own
  catalog.
- **UK tax basics (v1)** — account wrapper type, tax residency/band, and
  dividend withholding-tax fields captured on holdings; nothing beyond
  what's recorded is deducted automatically yet.
- **Performance charts** — since-inception current-value and
  invested-value lines per account/pie, with dividend history
  auto-synced from market data.
- **Search** — a unified catalog across stocks, ETFs, and benchmarks.
- **Support** — an in-app form for queries, ticker requests, and
  incorrect-data reports, filed straight to a private support tracker.
- **Sign-in experience** — Auth0-based authentication, a refreshed
  landing page, cookie consent with optional analytics, and dedicated
  error/offline pages.
- **Not yet live** — custom watchlists (placeholder page only).

See [CHANGELOG.md](../CHANGELOG.md) for the complete list of changes
behind this release.
