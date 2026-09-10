"""Routes a benchmark's own `key` (the S3 partition key
`packages/benchmark/config/benchmarks.*.yaml` already assigns it, e.g.
"SP500"/"FTSE100") to one of GitHub issue #68's per-index forecasting
schemas - see benchmark_schemas.yaml, the actual registry data this
module loads and matches against.

Unlike sector_registry.py (issue #66)/etf_type_registry.py (issue #67),
there's no substring/taxonomy matching here - a benchmark's own
already-configured `key` names it exactly, so routing is a plain
case-insensitive dict lookup. Also unlike etf_type_registry.py's 3-type
"Other" catch-all, there's **no generic fallback** here either - every
benchmark configured in benchmarks.*.yaml needs its own explicit schema
entry (see benchmark_schemas.yaml's own header comment for why), so
`route_benchmark` raises `UnroutableBenchmarkError` for any key not
explicitly registered, same "fail loudly" requirement issues #66/#67
already established for stock/ETF.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import yaml

_SCHEMAS_RESOURCE = "benchmark_schemas.yaml"


class UnroutableBenchmarkError(ValueError):
    """Raised by `route_benchmark` when `key` matches no registered
    benchmark schema - "fail loudly," per issue #68 (mirroring issues
    #66/#67's own routing requirement), rather than falling back to a
    generic template. Carries `key` as an attribute so a caller (e.g. the
    CLI) can log/report exactly which benchmark needs a new registry
    entry."""

    def __init__(self, key: str | None) -> None:
        self.key = key
        super().__init__(
            f"No forecasting schema routes benchmark key={key!r} - add an entry to "
            "benchmark_schemas.yaml rather than guessing a fallback."
        )


@dataclass(frozen=True)
class BenchmarkSchema:
    key: str
    label: str
    currency_sensitivity: str
    parameters: dict[str, list[str]]


def _load_schemas() -> list[BenchmarkSchema]:
    raw = yaml.safe_load(resources.files(__package__).joinpath(_SCHEMAS_RESOURCE).read_text())
    return [
        BenchmarkSchema(
            key=entry["key"],
            label=entry["label"],
            currency_sensitivity=entry["currency_sensitivity"],
            parameters=entry["parameters"],
        )
        for entry in raw["benchmarks"]
    ]


#: Loaded once at import time - the registry is fixed application data, not
#: something reloaded per call.
BENCHMARK_SCHEMAS: list[BenchmarkSchema] = _load_schemas()

_SCHEMAS_BY_KEY = {schema.key.upper(): schema for schema in BENCHMARK_SCHEMAS}


def route_benchmark(key: str | None) -> BenchmarkSchema:
    """Return the one `BenchmarkSchema` whose own `key` matches `key`
    (case-insensitively), or raise `UnroutableBenchmarkError` if none
    does."""
    schema = _SCHEMAS_BY_KEY.get((key or "").upper())
    if schema is None:
        raise UnroutableBenchmarkError(key)
    return schema
