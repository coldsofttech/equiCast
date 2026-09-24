# Release notes

User-facing summary of what shipped in each release. For the full,
implementation-level history (every change, fix, and why), see
[CHANGELOG.md](../CHANGELOG.md).

## v1.1.0 - 2026-09-23

Highlights:

- **UK dividend tax** — dividends are now taxed automatically per the UK
  rules: ISA/SIPP/LISA/JISA stay untaxed, GIA dividends use the £500
  tax-free allowance then the account holder's income tax band, and a new
  Dividend Allowance page (from the user menu) shows usage and tax
  deducted per UK tax year.
- **Account vendor tags** — accounts can now record a vendor/platform
  (e.g. Trading212, Chip), shown as a tag on the dashboard and accounts
  list.
- **Combined diversification chart** — an account's/pie's Sector and
  Industry breakdowns are now one chart, with drill-down from sector into
  industry.
- **Home page refresh** — highlights UK tax & allowance tracking, more
  implemented-feature chips in the hero, and a redesigned "Available
  today" section.
- **Sorted lists** — an account's portfolios/holdings and a pie's
  holdings now sort by current value, highest first.
- **Import improvements** — the import wizard's source picker shows real
  icons, and the review screen gets Select all/Unselect all.
- **More resilient ingestion** — a ticker/pair/benchmark that fails to
  fetch no longer takes down the rest of that ingestion run; failures are
  now reported as tracking issues automatically.
- **Various fixes** — including holdings/diversification charts no longer
  rendering when a holding has no shares yet, and several dividend
  allowance edge cases (edits, deletes, backdated transactions).

See [CHANGELOG.md](../CHANGELOG.md) for the complete list of changes
behind this release.

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
