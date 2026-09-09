"""Routes a stock's `sector`/`industry` (as yfinance's `.info` reports
them) to one of GitHub issue #66's 16 sector/sub-sector forecasting
schemas - see sector_schemas.yaml, the actual registry data this module
loads and matches against.

Per the issue: "Sector/sub-sector must be a required routing field before
parameter set is selected. No generic 'stock' fallback schema - an
unmapped industry should fail loudly (raise/flag), not silently default to
a generic template that doesn't fit it." `route_sector` does exactly that -
raises `UnroutableSectorError` rather than ever guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import yaml

_SCHEMAS_RESOURCE = "sector_schemas.yaml"


class UnroutableSectorError(ValueError):
    """Raised by `route_sector` when `sector`/`industry` matches none of
    the registered schemas - "fail loudly," per the issue, rather than
    falling back to a generic template. Carries `sector`/`industry` as
    attributes so a caller (e.g. the CLI) can log/report exactly which
    ticker and taxonomy value needs a new registry entry."""

    def __init__(self, sector: str | None, industry: str | None) -> None:
        self.sector = sector
        self.industry = industry
        super().__init__(
            f"No forecasting schema routes sector={sector!r}, industry={industry!r} - "
            "add an entry to sector_schemas.yaml rather than guessing a fallback."
        )


@dataclass(frozen=True)
class SectorSchema:
    key: str
    label: str
    sector: str
    industry_contains: tuple[str, ...]
    industry_excludes: tuple[str, ...]
    valuation_multiple: str | None
    parameters: dict[str, list[str]]

    def matches(self, sector: str | None, industry: str | None) -> bool:
        if sector != self.sector:
            return False
        industry_text = (industry or "").lower()
        if self.industry_excludes and any(
            excluded.lower() in industry_text for excluded in self.industry_excludes
        ):
            return False
        if not self.industry_contains:
            return True
        return any(substr.lower() in industry_text for substr in self.industry_contains)


def _load_schemas() -> list[SectorSchema]:
    raw = yaml.safe_load(resources.files(__package__).joinpath(_SCHEMAS_RESOURCE).read_text())
    return [
        SectorSchema(
            key=entry["key"],
            label=entry["label"],
            sector=entry["sector"],
            industry_contains=tuple(entry.get("industry_contains") or ()),
            industry_excludes=tuple(entry.get("industry_excludes") or ()),
            valuation_multiple=entry.get("valuation_multiple"),
            parameters=entry["parameters"],
        )
        for entry in raw["sectors"]
    ]


#: Loaded once at import time - the registry is fixed application data, not
#: something reloaded per call.
SECTOR_SCHEMAS: list[SectorSchema] = _load_schemas()


def route_sector(sector: str | None, industry: str | None) -> SectorSchema:
    """Return the one `SectorSchema` matching `sector`/`industry`, or raise
    `UnroutableSectorError` if none does. Financial Services/Healthcare/
    Real Estate each have multiple sub-sector entries and no bare
    sector-only entry, so a stock in one of those three sectors whose
    industry matches none of its sub-schemas is unroutable too, not
    silently routed to a same-sector sibling."""
    for schema in SECTOR_SCHEMAS:
        if schema.matches(sector, industry):
            return schema
    raise UnroutableSectorError(sector, industry)
