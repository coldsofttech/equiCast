"""Routes a future's own `key` (the S3 partition key
`packages/future/config/futures.*.yaml` already assigns it, e.g. "GOLD")
to one of GitHub issue #143's 5 commodity-class forecasting schemas - see
commodity_class_schemas.yaml, the actual registry data this module loads
and matches against.

Unlike sector_registry.py (issue #66)/etf_type_registry.py (issue #67),
there's no substring/taxonomy matching here - each schema declares an
explicit `symbols` list (the issue's own table is organized by class,
listing exactly which futures belong to it), so routing is a plain
case-insensitive dict lookup, same shape benchmark_registry.py (issue #68)
uses. Also like benchmark_registry.py, there's **no generic fallback** -
every future configured in futures.*.yaml needs its own class membership
declared explicitly, so `route_commodity_class` raises
`UnroutableCommodityError` for any key not found in any schema's
`symbols`, same "fail loudly" requirement issues #66/#67/#68 already
established.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import yaml

_SCHEMAS_RESOURCE = "commodity_class_schemas.yaml"


class UnroutableCommodityError(ValueError):
    """Raised by `route_commodity_class` when `key` matches no registered
    commodity class - "fail loudly," per issue #143 (mirroring issues
    #66/#67/#68's own routing requirement), rather than falling back to a
    generic template. Carries `key` as an attribute so a caller (e.g. the
    CLI) can log/report exactly which future needs a new registry entry."""

    def __init__(self, key: str | None) -> None:
        self.key = key
        super().__init__(
            f"No forecasting schema routes future key={key!r} - add it to a commodity "
            "class's symbols list in commodity_class_schemas.yaml rather than guessing a "
            "fallback."
        )


@dataclass(frozen=True)
class CommodityClassSchema:
    key: str
    label: str
    symbols: tuple[str, ...]
    parameters: dict[str, list[str]]


def _load_schemas() -> list[CommodityClassSchema]:
    raw = yaml.safe_load(resources.files(__package__).joinpath(_SCHEMAS_RESOURCE).read_text())
    return [
        CommodityClassSchema(
            key=entry["key"],
            label=entry["label"],
            symbols=tuple(entry["symbols"]),
            parameters=entry["parameters"],
        )
        for entry in raw["commodity_classes"]
    ]


#: Loaded once at import time - the registry is fixed application data, not
#: something reloaded per call.
COMMODITY_CLASS_SCHEMAS: list[CommodityClassSchema] = _load_schemas()

_SCHEMA_BY_SYMBOL = {
    symbol.upper(): schema for schema in COMMODITY_CLASS_SCHEMAS for symbol in schema.symbols
}


def route_commodity_class(key: str | None) -> CommodityClassSchema:
    """Return the one `CommodityClassSchema` whose own `symbols` contains
    `key` (case-insensitively), or raise `UnroutableCommodityError` if
    none does."""
    schema = _SCHEMA_BY_SYMBOL.get((key or "").upper())
    if schema is None:
        raise UnroutableCommodityError(key)
    return schema
