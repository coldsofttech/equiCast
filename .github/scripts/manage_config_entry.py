"""Adds/updates/deletes one entry in a stock/etf/fx/benchmark ingestion
config YAML file (equicast-support#6) — the scriptable half of
manage-config-fix.yml's repository_dispatch payload, fired once a
maintainer replies to a support-filed "[Ticker request]" issue with what
to change (see equicast-support's dispatch_config_change.sh). Never
touches `main` directly; the workflow commits this script's edit on its
own branch and opens a PR (see that workflow for why).

Uses `ruamel.yaml` in round-trip mode rather than PyYAML, specifically to
avoid the "YAML formatting/ordering preservation on write" problem the
issue calls out — `yaml.safe_load`/`yaml.dump` would silently strip every
comment in these files and reformat quoting/indentation, turning a
one-line config change into a noisy whole-file diff. Not a workspace
dependency (no package here actually needs it at runtime) — the workflow
installs it ephemerally via `uv run --with ruamel.yaml`.

Each asset class's config has its own list key and entry shape:

- stock/etf: `tickers: [str, ...]` — a bare ticker string, or a
  `{ticker, isin?, tax_domicile?}` mapping when either needs a manual
  override (see stock-pipeline.md/etf-pipeline.md). Matched by `ticker`,
  case-insensitively.
- fx: `pairs: [{from, to}, ...]`. Matched by the exact `(from, to)` pair;
  `update` is rejected outright — a pair has no overridable fields to
  update, unlike stock/etf/benchmark.
- benchmark: `benchmarks: [{key, symbol}, ...]`. Matched by `key`.

`add` raises if the entry already exists (use `update` instead); `update`/
`delete` raise if it doesn't (nothing to update/delete) — the "idempotency
/ already-exists / not-found" handling the issue calls out, surfaced as a
clear error rather than a silent no-op either way.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

REPO_ROOT = Path(__file__).resolve().parents[2]

#: (list_key, file_path_template) per asset class - the template's `{env}`
#: is filled in with "dev"/"prod" (see main()). Deliberately only these
#: two, of the three suffixes local-dev.ps1 knows about - `.local.yaml` is
#: gitignored (a developer's own machine-local overrides), so a workflow
#: committing to it would have nothing to commit.
_CONFIGS: dict[str, tuple[str, str]] = {
    "stock": ("tickers", "packages/stock/config/stocks.{env}.yaml"),
    "etf": ("tickers", "packages/etf/config/etfs.{env}.yaml"),
    "fx": ("pairs", "packages/fx/config/fx_pairs.{env}.yaml"),
    "benchmark": ("benchmarks", "packages/benchmark/config/benchmarks.{env}.yaml"),
}


class ConfigEntryError(Exception):
    """Raised for any user-facing failure (bad key, already exists, not
    found, wrong flags for this asset class) - caught once in main() and
    printed without a traceback, since none of these are bugs in this
    script."""


def _ticker_key(entry: Any) -> str:
    """A tickers-list entry is either a bare string or a
    `{ticker, isin?, tax_domicile?}` mapping - either way, its identity is
    the ticker, compared case-insensitively (the config files themselves
    are consistently uppercase, but this is friendlier to a typo'd
    lowercase input than silently creating a duplicate)."""
    ticker = entry if isinstance(entry, str) else entry.get("ticker", "")
    return str(ticker).upper()


def _manage_tickers(
    data: CommentedMap,
    list_key: str,
    action: str,
    key: str,
    isin: str | None,
    tax_domicile: str | None,
) -> str:
    tickers = data[list_key]
    key = key.upper()
    index = next((i for i, e in enumerate(tickers) if _ticker_key(e) == key), None)

    if action == "add":
        if index is not None:
            raise ConfigEntryError(f"'{key}' already exists - use action=update instead.")
        if isin or tax_domicile:
            entry: Any = CommentedMap({"ticker": key})
            if isin:
                entry["isin"] = isin
            if tax_domicile:
                entry["tax_domicile"] = tax_domicile
        else:
            entry = key
        tickers.append(entry)
        return f"Added '{key}'" + (
            f" (isin={isin}, tax_domicile={tax_domicile})" if entry != key else ""
        )

    if index is None:
        raise ConfigEntryError(f"'{key}' not found - nothing to {action}.")

    if action == "delete":
        del tickers[index]
        return f"Deleted '{key}'"

    # action == "update"
    if not isin and not tax_domicile:
        raise ConfigEntryError("update requires --isin and/or --tax-domicile - nothing was given.")
    existing = tickers[index]
    entry = CommentedMap({"ticker": key}) if isinstance(existing, str) else existing
    if isin:
        entry["isin"] = isin
    if tax_domicile:
        entry["tax_domicile"] = tax_domicile
    tickers[index] = entry
    return (
        f"Updated '{key}' (isin={isin or entry.get('isin')}, "
        f"tax_domicile={tax_domicile or entry.get('tax_domicile')})"
    )


def _manage_fx_pairs(data: CommentedMap, list_key: str, action: str, key: str) -> str:
    try:
        from_ccy, to_ccy = (part.strip().upper() for part in key.split(":", 1))
    except ValueError as exc:
        raise ConfigEntryError(
            f"fx --key must be 'FROM:TO' (e.g. 'GBP:USD'), got '{key}'."
        ) from exc

    pairs = data[list_key]
    index = next(
        (i for i, p in enumerate(pairs) if p.get("from") == from_ccy and p.get("to") == to_ccy),
        None,
    )

    if action == "update":
        raise ConfigEntryError("fx pairs have no overridable fields - only add/delete apply.")
    if action == "add":
        if index is not None:
            raise ConfigEntryError(f"'{from_ccy}:{to_ccy}' already exists.")
        pairs.append(CommentedMap({"from": from_ccy, "to": to_ccy}))
        return f"Added '{from_ccy}:{to_ccy}'"
    if index is None:
        raise ConfigEntryError(f"'{from_ccy}:{to_ccy}' not found - nothing to delete.")
    del pairs[index]
    return f"Deleted '{from_ccy}:{to_ccy}'"


def _manage_benchmarks(
    data: CommentedMap, list_key: str, action: str, key: str, symbol: str | None
) -> str:
    benchmarks = data[list_key]
    index = next((i for i, b in enumerate(benchmarks) if b.get("key") == key), None)

    if action == "add":
        if index is not None:
            raise ConfigEntryError(f"'{key}' already exists - use action=update instead.")
        if not symbol:
            raise ConfigEntryError("add requires --symbol (the yfinance ticker to fetch).")
        benchmarks.append(CommentedMap({"key": key, "symbol": DoubleQuotedScalarString(symbol)}))
        return f"Added '{key}' (symbol={symbol})"

    if index is None:
        raise ConfigEntryError(f"'{key}' not found - nothing to {action}.")

    if action == "delete":
        del benchmarks[index]
        return f"Deleted '{key}'"

    # action == "update"
    if not symbol:
        raise ConfigEntryError("update requires --symbol - nothing was given.")
    benchmarks[index]["symbol"] = DoubleQuotedScalarString(symbol)
    return f"Updated '{key}' (symbol={symbol})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-class", required=True, choices=sorted(_CONFIGS))
    parser.add_argument("--environment", required=True, choices=["dev", "prod"])
    parser.add_argument("--action", required=True, choices=["add", "update", "delete"])
    parser.add_argument(
        "--key",
        required=True,
        help="Ticker (stock/etf), 'FROM:TO' pair (fx), or benchmark key (benchmark).",
    )
    parser.add_argument("--isin", default=None, help="stock/etf only.")
    parser.add_argument("--tax-domicile", default=None, help="stock only.")
    parser.add_argument("--symbol", default=None, help="benchmark only - the yfinance ticker.")
    args = parser.parse_args()

    list_key, path_template = _CONFIGS[args.asset_class]
    path = REPO_ROOT / path_template.format(env=args.environment)
    if not path.exists():
        raise ConfigEntryError(f"{path} does not exist.")

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    try:
        if args.asset_class in ("stock", "etf"):
            summary = _manage_tickers(
                data, list_key, args.action, args.key, args.isin, args.tax_domicile
            )
        elif args.asset_class == "fx":
            summary = _manage_fx_pairs(data, list_key, args.action, args.key)
        else:
            summary = _manage_benchmarks(data, list_key, args.action, args.key, args.symbol)
    except ConfigEntryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)

    print(f"{summary} in {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
