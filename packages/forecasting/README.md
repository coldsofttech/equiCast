# equicast-forecasting

Projects a symbol's future dividend payouts from its actual dividend
history, built on [equicast-dividends](../dividends/README.md).

## Usage

```python
from equicast_dividends import DividendsClient
from equicast_forecasting import dividends

history = DividendsClient("AAPL").dividends(full_load=True)
dividends(history)
# [{"ticker": "AAPL", "currency": "USD", "ex_dividend_date": "2026-05-12",
#   "price": 0.26, "dividend_frequency": "quarterly",
#   "last_updated": "2026-08-30T09:00:00+00:00", "source": "equicast"},
#  ...]
```

`dividends(records, years=10)` takes a symbol's dividend records — the same
shape `DividendsClient.dividends()` returns — and projects up to `years`
years of future payouts forward from them. Returns `[]` when there isn't a
dependable cadence to extend: the same `"irregular"`/`"not_applicable"`
cases [`equicast-dividends`' `dividend_frequency()`](../dividends/README.md#dividend_frequency)
flags (a genuinely erratic payer, or fewer than 2 recorded payouts) aren't
projected forward — a classification this uncertain about the *past*
shouldn't be extrapolated years into the *future*.

Each returned record is shaped like a real dividend record (`ticker`,
`currency`, `ex_dividend_date`, `price`, `last_updated`, `source`), plus a
`dividend_frequency` field naming the cadence assumption used. `source` is
always `"equicast"`, never `"yfinance"` — this is a computed projection, not
observed data.

### How the dates are projected

Each projected payout continues the ticker's *actual* empirical cadence
forward from its most recent real payout —
[`median_payout_gap_days()`](../dividends/README.md#median_payout_gap_days),
the same day-gap `dividend_frequency()` classifies, not a fixed per-label
constant. A payer whose real median gap is 84 days keeps stepping by 84, not
by "quarterly"'s canonical ~91 — so the projected calendar doesn't
gradually drift away from the ticker's real one.

### How the amounts are projected

Every projected payout starts from the most recent *actual* amount, then
compounds once per calendar year crossed (relative to that last actual
payout) at a trailing dividend growth rate:

1. Sum actual payouts into one total per full calendar year (the current
   year is excluded — it may not be complete yet, and including a partial
   year would understate its eventual total).
2. Compare the oldest to the newest of the most recent 6 such years (5
   year-over-year steps) as a CAGR: `(newest / oldest) ** (1 / years) - 1`.
3. Clamp the result to ±50%/year, so one outlier historical year (a special
   dividend inflating a single year's total, or a one-off cut) can't produce
   an implausible runaway compound over a long horizon.
4. Fall back to `0.0` (flat — every projected payout repeats the last actual
   amount) if there are fewer than 2 full years to compare, or the older
   year's total is `0` (nothing meaningful to ratio against — e.g. payouts
   only started partway through that year).

This is a projection from historical *rate*, not a prediction of specific
future dividend announcements — treat it as "if this ticker's recent cadence
and growth trend continue unchanged," not as authoritative. It will be
visibly wrong around any real dividend cut, suspension, or cadence change,
same as any trend extrapolation.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
