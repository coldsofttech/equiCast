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
lookup — this matches what the broker actually charged. Trading 212 quotes
its rate the human-facing way ("£1 = $1.34"); equicast automatically
inverts it to the direction it stores internally, so you don't need to do
anything about this yourself.

Trading 212's own `Stamp duty reserve tax` and `Currency conversion fee`
columns are also imported (GitHub issues #100/#101) — read at face value as
already being in your account's default currency; their `Currency (...)`
companion columns are for your own reference only and aren't used to
convert anything.

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
| `sdrt`           | No       | UK Stamp Duty Reserve Tax, in your default currency (BUY rows only) |
| `fx_fee`         | No       | Currency-conversion fee, in your default currency    |
| `external_id`    | No       | Your own identifier for the row, used for dedup      |

`fx_rate`, if you supply it, must be in the **converted-per-native** direction — how many units of your default currency one unit of the instrument's native currency is worth (the same direction equicast stores/uses internally). This is the *opposite* of how brokers and FX quotes usually show a rate to a person ("£1 = $1.34") — if you have a rate quoted that way, invert it (`1 / rate`) before putting it in this column. The Trading 212 preset does this inversion for you automatically, since its export is quoted the human-facing way.

`sdrt`/`fx_fee` (GitHub issues #100/#101), unlike every other monetary
column here, are always in your own default currency, never the
instrument's native currency — there's no conversion to do.

## Matching tickers

equicast matches an imported row against its own market-data catalog by
ISIN first when the row has one (Trading 212 exports always do) — ticker
symbols aren't unique across exchanges/asset classes, so ISIN is the more
reliable match. Only when there's no ISIN, or it doesn't resolve, does
equicast fall back to matching by ticker. A row that resolves by neither
(or resolves to the wrong instrument) can be corrected during review by
searching for the right one.

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
