"""UK dividend tax calculation engine (GitHub issue #212).

Follow-up to GitHub issue #94, which landed the data model this module's
single entry point (`compute_uk_dividend_tax`) consumes: `wrapper_type`/
`account_type` (the closed ISA/GIA/SIPP/LISA/JISA enum), a user's
`income_tax_band`, a holding's `tax_domicile`-derived `default_withholding_
pct`, and a per-holding `tax_override_pct`. #94 deliberately stopped short
of the actual calculation (allowance, band rates, tax-year tracking) — this
module is that calculation.

Pure and stateless by design: it takes a snapshot of everything it needs
(including the caller's running `allowance_used_ytd` for the relevant UK
tax year) and returns a breakdown, including the new `allowance_used_ytd`
the caller should persist — it never reads or writes any store itself. Who
calls it, when, and what happens to that returned allowance figure is
entirely up to the caller (see `backend.transactions.views._apply_uk_
dividend_tax`, which calls this once per DIVIDEND transaction created and
persists the allowance delta via `UserProfileClient.add_dividend_allowance_
used`)."""

from __future__ import annotations

from datetime import date
from typing import Any

#: The UK dividend allowance, per user per UK tax year (6 Apr-5 Apr) — the
#: first £500 of taxable (i.e. post-allowance-exempt-wrapper, post-
#: withholding) dividend income in a tax year is untaxed. Never household-
#: pooled (GitHub issue #212's "Out of scope") — always computed per-user.
UK_DIVIDEND_ALLOWANCE = 500.0

#: `wrapper_type`/`account_type` values (GitHub issue #94) that pay 0% tax
#: on dividend income regardless of amount — no allowance is ever consumed
#: for a holding under one of these. Everything else (i.e. `GIA`) is
#: taxable, subject to the allowance/band-rate calculation below.
UK_TAX_EXEMPT_WRAPPER_TYPES = frozenset({"ISA", "SIPP", "LISA", "JISA"})

#: A GIA holding's dividend tax rate on the amount over the allowance, by
#: the user's self-declared `income_tax_band` (identity/views.py's
#: INCOME_TAX_BANDS) — 2024/25 UK dividend tax rates. `NONE` (no income tax
#: liability) stays untaxed, same as the exempt wrapper types, just via a
#: 0% rate here instead of skipping the calculation entirely, since a
#: `NONE`-band GIA holding still consumes the allowance up to its net
#: dividend amount (the allowance itself isn't income-band-conditional).
UK_DIVIDEND_TAX_RATES: dict[str, float] = {
    "NONE": 0.0,
    "BASIC": 0.0875,
    "HIGHER": 0.3375,
    "ADDITIONAL": 0.3935,
}


def uk_tax_year_label(iso_date: str) -> str:
    """Return the UK tax year `iso_date` (a `"YYYY-MM-DD"` string, e.g. a
    DIVIDEND transaction's `date`) falls in, as a `"YYYY-YY"` label (e.g.
    `"2026-27"` for the tax year running 6 Apr 2026-5 Apr 2027) — the key
    `compute_uk_dividend_tax`'s caller looks up/stores `allowance_used_ytd`
    under (see `UserProfileClient.add_dividend_allowance_used`'s
    `dividend_allowance_used_by_tax_year` map). A date on or after 6 Apr
    belongs to the tax year starting that same calendar year; a date before
    6 Apr belongs to the one starting the previous calendar year."""
    parsed = date.fromisoformat(iso_date)
    start_year = parsed.year if (parsed.month, parsed.day) >= (4, 6) else parsed.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def compute_uk_dividend_tax(
    *,
    wrapper_type: str,
    tax_domicile: str | None,
    default_withholding_pct: float | None,
    tax_override_pct: float | None,
    income_tax_band: str,
    gross_amount: float,
    allowance_used_ytd: float,
) -> dict[str, Any]:
    """Compute one dividend's UK tax treatment (GitHub issue #212).

    `wrapper_type`: the holding's account's `account_type` (GitHub issue
    #94) — `ISA`/`SIPP`/`LISA`/`JISA` short-circuit to 0% tax, no allowance
    consumed. Anything else (`GIA`) runs the full calculation below.

    `tax_domicile`/`default_withholding_pct`: the holding's ticker-derived
    withholding rate (`MarketDataClient.enrich_holdings`, GitHub issue #94)
    — applied only when `tax_override_pct` is unset and `tax_domicile`
    isn't `"UK"`.

    `tax_override_pct`: a holding-in-account's own override (GitHub issue
    #94's `update_holding_tax_override`) — takes precedence over the
    domicile-derived rate entirely when set (not just when it disagrees).

    `income_tax_band`: the user's self-declared UK income tax band
    (identity/views.py's INCOME_TAX_BANDS / `UK_DIVIDEND_TAX_RATES`'s keys)
    — the rate applied to whatever's left after the allowance.

    `gross_amount`: the dividend's cash amount, in GBP (this v1 assumes the
    caller's `default_currency` already IS GBP — see GitHub issue #212;
    calling this for a non-GBP `default_currency` would tax the wrong
    figure against GBP-denominated thresholds, so callers should skip the
    call entirely in that case, not pass a converted-to-something-else
    amount here).

    `allowance_used_ytd`: how much of the £500 UK_DIVIDEND_ALLOWANCE this
    user has already consumed in `gross_amount`'s UK tax year (see
    `uk_tax_year_label`) — the caller's job to look up (e.g. from
    `UserProfileClient`'s `dividend_allowance_used_by_tax_year`) and, from
    the returned `new_allowance_used_ytd`, persist back.

    Returns a breakdown dict: `wrapper_taxable` (whether this wrapper type
    is taxable at all), `withholding_pct_applied`/`withholding_amount`,
    `net_of_withholding` (`gross_amount` minus withholding),
    `allowance_consumed` (how much of `net_of_withholding` the remaining
    allowance covered), `taxable_amount` (what's left after the allowance),
    `tax_rate_applied`/`tax_amount`, `net_amount` (`net_of_withholding`
    minus `tax_amount` — the actual cash the user nets from this dividend),
    and `new_allowance_used_ytd` (`allowance_used_ytd + allowance_consumed`,
    for the caller to persist)."""
    if wrapper_type in UK_TAX_EXEMPT_WRAPPER_TYPES:
        return {
            "wrapper_taxable": False,
            "withholding_pct_applied": 0.0,
            "withholding_amount": 0.0,
            "net_of_withholding": gross_amount,
            "allowance_consumed": 0.0,
            "taxable_amount": 0.0,
            "tax_rate_applied": 0.0,
            "tax_amount": 0.0,
            "net_amount": gross_amount,
            "new_allowance_used_ytd": allowance_used_ytd,
        }

    if tax_override_pct is not None:
        withholding_pct = tax_override_pct
    elif tax_domicile is not None and tax_domicile != "UK":
        withholding_pct = default_withholding_pct or 0.0
    else:
        withholding_pct = 0.0

    withholding_amount = gross_amount * (withholding_pct / 100)
    net_of_withholding = gross_amount - withholding_amount

    allowance_remaining = max(0.0, UK_DIVIDEND_ALLOWANCE - allowance_used_ytd)
    allowance_consumed = min(net_of_withholding, allowance_remaining)
    taxable_amount = net_of_withholding - allowance_consumed

    tax_rate = UK_DIVIDEND_TAX_RATES[income_tax_band]
    tax_amount = taxable_amount * tax_rate
    net_amount = net_of_withholding - tax_amount

    return {
        "wrapper_taxable": True,
        "withholding_pct_applied": withholding_pct,
        "withholding_amount": withholding_amount,
        "net_of_withholding": net_of_withholding,
        "allowance_consumed": allowance_consumed,
        "taxable_amount": taxable_amount,
        "tax_rate_applied": tax_rate,
        "tax_amount": tax_amount,
        "net_amount": net_amount,
        "new_allowance_used_ytd": allowance_used_ytd + allowance_consumed,
    }
