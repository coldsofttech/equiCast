"""Classify a symbol's dividend-payout cadence from its ex-dividend-date history."""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any

#: (label, (min_days, max_days)) inclusive day-gap bands a payout cadence's median
#: gap is matched against, ordered by increasing cadence length. Boundaries sit at
#: the midpoint between each pair of idealized cadences (weekly ~7d, monthly ~30d,
#: quarterly ~91d, half-yearly ~182d, yearly ~365d) rather than a fixed +/-
#: percentage, so a real payer with one slightly early/late/skipped payout still
#: lands in its normal band. A median outside every band (too frequent to be
#: meaningful, or too sparse/inconsistent to trust) falls through to "irregular".
_BANDS: list[tuple[str, tuple[int, int]]] = [
    ("weekly", (3, 18)),
    ("monthly", (19, 60)),
    ("quarterly", (61, 136)),
    ("half_yearly", (137, 273)),
    ("yearly", (274, 450)),
]

#: Fewer than this many historical payouts means fewer than one gap can be
#: measured (2 payouts = 1 gap) -- below it there's nothing to classify, so
#: callers get "not_applicable" rather than a guess from a single data point.
_MIN_PAYOUTS = 2

#: Only the most recent this many payouts are used to compute gaps -- older
#: history (e.g. a payer that switched from annual to quarterly years ago)
#: shouldn't outvote the ticker's actual current cadence.
_SAMPLE_SIZE = 10


def median_payout_gap_days(records: list[dict[str, Any]]) -> float | None:
    """The median day-gap between the most recent `_SAMPLE_SIZE` payouts in
    `records` (as returned by `DividendsClient.dividends()`), or however many
    `records` has, down to `_MIN_PAYOUTS`. Sorted by `ex_dividend_date`
    regardless of `records`' own order.

    Returns `None` if there are fewer than `_MIN_PAYOUTS` payouts to measure a
    gap from at all (no dividend history, or a single just-started one) --
    the same case `dividend_frequency()` reports as `"not_applicable"`.
    Median rather than mean so one unusually long/short gap in the sample
    doesn't shift the result on its own.
    """
    dates = sorted(date.fromisoformat(record["ex_dividend_date"]) for record in records)
    if len(dates) < _MIN_PAYOUTS:
        return None

    recent = dates[-_SAMPLE_SIZE:]
    gaps = [(later - earlier).days for earlier, later in zip(recent, recent[1:])]
    return median(gaps)


def dividend_frequency(records: list[dict[str, Any]]) -> str:
    """Classify `records` (as returned by `DividendsClient.dividends()`) into a
    payout cadence: `"weekly"`, `"monthly"`, `"quarterly"`, `"half_yearly"`,
    `"yearly"`, `"irregular"` (a real, still-active payer whose recent gaps don't
    fit any of the above -- e.g. a one-off special dividend thrown into an
    otherwise-quarterly schedule skews the sample, or a genuinely erratic payer),
    or `"not_applicable"` (fewer than 2 recorded payouts to measure a gap from at
    all -- no dividend history, or a single just-started one).

    Matches `median_payout_gap_days(records)` against `_BANDS`; `None` from that
    (fewer than `_MIN_PAYOUTS` payouts) maps to `"not_applicable"` here.
    """
    median_gap = median_payout_gap_days(records)
    if median_gap is None:
        return "not_applicable"

    for label, (low, high) in _BANDS:
        if low <= median_gap <= high:
            return label
    return "irregular"
