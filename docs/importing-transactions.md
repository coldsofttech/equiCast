# Importing transactions

equiCast can bulk-import transactions from a file instead of entering each
one by hand — from **Settings → Import transactions**. Two sources are
supported:

- **Trading 212 export** — a statement exported directly from the Trading
  212 app.
- **Generic CSV** — a minimal schema you can build yourself from any other
  broker's data, or a spreadsheet.

Either way, the flow is the same: upload a file, review what equicast
parsed (grouping rows by ticker, letting you pick which holdings to import
and which account or pie to put each one in), then commit.

Dividend/interest rows in a broker export are **never imported** — equicast
already backfills dividend transactions automatically from paid-dividend
history once a buy/sell position exists, so importing a broker's own
dividend rows would double-count them.

## Trading 212 export

In the Trading 212 app:

1. Go to **Settings → History → Export**.
2. Pick the time period to export.
3. Under **Include data**, check **Orders** and **Transactions**.
4. **Dividends** and **Interest** can be left checked or unchecked either
   way — equicast ignores those rows regardless (see above).
5. Export and download the CSV, then upload it in equicast's import wizard.

Only buy/sell rows are used. Trading 212's own exchange rate for a row is
used as that transaction's FX rate, rather than equicast's own historical
lookup — this matches what the broker actually charged.

## Generic CSV

Build your own CSV with these columns:

| Column          | Required | Notes                                              |
| ---------------- | -------- | --------------------------------------------------- |
| `date`           | Yes      | `YYYY-MM-DD`                                         |
| `ticker`         | Yes      |                                                       |
| `type`           | Yes      | `BUY` or `SELL` only                                 |
| `no_of_shares`   | Yes      | Positive number                                      |
| `price_native`   | Yes      | Positive number, in the instrument's own currency    |
| `asset_class`    | No       | `stock` or `etf` — helps equicast resolve the ticker |
| `currency`       | No       | Informational only, not used to resolve FX           |
| `fx_rate`        | No       | Overrides equicast's own historical FX lookup        |
| `external_id`    | No       | Your own identifier for the row, used for dedup      |

## Matching tickers

equicast matches an imported row's ticker against its own market-data
catalog. This is ticker-based only for now — a ticker that doesn't resolve
(or resolves to the wrong instrument) can be corrected during review by
searching for the right one. ISIN-based matching is a planned follow-up
(the ticker/ISIN ambiguity this would resolve is tracked separately).

## AVERAGE vs TRANSACTION accounts

Your account's transaction type (Settings → Transaction type) determines
how an import is applied to a holding:

- **TRANSACTION** accounts: every imported row becomes its own buy/sell
  entry, same as entering them one at a time. Re-uploading the same (or an
  overlapping) export skips rows already imported.
- **AVERAGE** accounts: every imported row for a holding is folded into one
  weighted-average position. If the target holding already has a position,
  the import **extends** it — e.g. an existing 2 shares plus an imported 3
  shares becomes 5, at a recombined weighted-average price — rather than
  replacing it. Re-uploading the same export in an AVERAGE account will add
  the shares again, since there's no per-row tracking to detect a repeat
  import the way TRANSACTION accounts have; take care not to import the
  same file twice.
