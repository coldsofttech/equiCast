"""Routes an ETF's `category` (as yfinance's `.info` reports it, a
Morningstar category string like "Large Blend"/"Foreign Large Blend"/
"Technology") to one of GitHub issue #67's three ETF-type forecasting
schemas - see etf_type_schemas.yaml, the actual registry data this module
loads and matches against. Same "fail loudly, no generic fallback"
philosophy sector_registry.py (issue #66) already established for stock:
`route_etf_type` raises `UnroutableEtfTypeError` rather than ever guessing
a type for a category it doesn't recognize.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import yaml

_SCHEMAS_RESOURCE = "etf_type_schemas.yaml"

#: Routing precedence: most-specific type first. Several of Broad/S&P's
#: own style-box substrings (e.g. "Large Blend") are themselves substrings
#: of a regional category ("Foreign Large Blend") - checking regional
#: before broad avoids that false-positive match. Thematic/Focused's
#: sector-name substrings don't collide with either, but are checked first
#: regardless, since a sector-specific category is the most unambiguous
#: signal available.
ROUTING_ORDER = ("thematic_focused", "ftse_regional", "broad_sp")


class UnroutableEtfTypeError(ValueError):
    """Raised by `route_etf_type` when `category` matches none of the
    registered ETF-type schemas - "fail loudly," per issue #67 (mirroring
    issue #66's own stock routing requirement), rather than falling back
    to a generic template. Carries `category` as an attribute so a caller
    (e.g. the CLI) can log/report exactly which ETF and category value
    needs a new registry entry."""

    def __init__(self, category: str | None) -> None:
        self.category = category
        super().__init__(
            f"No forecasting schema routes category={category!r} - add an entry to "
            "etf_type_schemas.yaml rather than guessing a fallback."
        )


@dataclass(frozen=True)
class EtfTypeSchema:
    key: str
    label: str
    category_contains: tuple[str, ...]
    parameters: dict[str, list[str]]

    def matches(self, category: str | None) -> bool:
        category_text = (category or "").lower()
        return any(substr.lower() in category_text for substr in self.category_contains)


def _load_schemas() -> tuple[list[str], list[EtfTypeSchema]]:
    raw = yaml.safe_load(resources.files(__package__).joinpath(_SCHEMAS_RESOURCE).read_text())
    schemas = [
        EtfTypeSchema(
            key=entry["key"],
            label=entry["label"],
            category_contains=tuple(entry.get("category_contains") or ()),
            parameters=entry["parameters"],
        )
        for entry in raw["etf_types"]
    ]
    return list(raw["cross_cutting"]), schemas


#: Loaded once at import time - the registry is fixed application data, not
#: something reloaded per call.
CROSS_CUTTING_PARAMETERS: list[str]
ETF_TYPE_SCHEMAS: list[EtfTypeSchema]
CROSS_CUTTING_PARAMETERS, ETF_TYPE_SCHEMAS = _load_schemas()

_SCHEMAS_BY_KEY = {schema.key: schema for schema in ETF_TYPE_SCHEMAS}


def route_etf_type(category: str | None) -> EtfTypeSchema:
    """Return the one `EtfTypeSchema` matching `category`, checked in
    `ROUTING_ORDER` (most-specific first), or raise `UnroutableEtfTypeError`
    if none does."""
    for key in ROUTING_ORDER:
        schema = _SCHEMAS_BY_KEY[key]
        if schema.matches(category):
            return schema
    raise UnroutableEtfTypeError(category)
