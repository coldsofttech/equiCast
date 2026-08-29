"""Shared decimal-precision policy for numeric fields across equicast's market-data packages."""

from __future__ import annotations

#: Every numeric field equicast computes or re-emits is rounded to this many
#: decimal places. Comfortably above FX's ~5-decimal (pipette) precision and
#: the ~4-6 decimals meaningful for risk/performance ratios, while cutting off
#: float64 representation noise beyond that (e.g. 1.3504753112792969).
DECIMAL_PRECISION = 8


def round_value(value: float | None, precision: int = DECIMAL_PRECISION) -> float | None:
    """Round `value` to `precision` decimal places, passing `None` through."""
    return round(value, precision) if value is not None else None
