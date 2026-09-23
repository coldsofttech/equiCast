"""CLI: find the FX pairs a stock/ETF catalog's holding currencies need but
fx_pairs.<env>.yaml doesn't configure (equicast-support#164).

A holding priced in currency C can only be shown in a UI currency T (the
closed set the Settings picker offers - frontend/src/config/currencies.json)
if C->T is published, and T->C is needed for the reverse conversion (e.g.
a cash flow in the user's currency back into the holding's). So for every
holding currency C and every UI currency T != C, *both* directed pairs
`C:T` and `T:C` must be configured; each one that isn't is reported as its
own missing pair, along with the tickers that need it.

Used by stock-ingestion.yml/etf-ingestion.yml's build-catalog job to feed
.github/scripts/sync-missing-fx-pair-issues.sh, which opens one
equicast-support issue per missing pair. Prints JSON:
`{"missing": [{"from", "to", "tickers"}, ...], "configured": ["GBP:USD", ...]}`
- `configured` lets the sync script close an issue once its pair has been
added, without re-parsing the YAML itself.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from equicast_fx.config import FxPair, load_fx_pairs

logger = logging.getLogger(__name__)

#: yfinance's pence-sterling code for LSE-listed instruments - not a real
#: ISO-4217 currency, just GBP / 100, which equicast_core.client converts
#: via the ordinary GBP rate (see its GBP_MINOR_CURRENCY). So a GBp holding
#: needs exactly the pairs a GBP one does. Duplicated rather than imported
#: to keep equicast-fx free of an equicast-core dependency.
_CURRENCY_ALIASES = {"GBp": "GBP"}

#: Anything else that isn't a plain 3-letter uppercase code (e.g. ZAc/ILA
#: minor units - equicast-support#176) is skipped with a warning rather than
#: reported as an unfixable "ZAc:GBP" pair.
_ISO_CURRENCY = re.compile(r"^[A-Z]{3}$")


def pair_key(from_currency: str, to_currency: str) -> str:
    """`FROM:TO` - the same key format manage_config_entry.py's `--key`
    takes for fx, so a missing-pair issue can be fed straight to it."""
    return f"{from_currency}:{to_currency}"


def load_ui_currencies(path: Path) -> list[str]:
    """Parse frontend/src/config/currencies.json (`[{code, name}, ...]`)."""
    return [entry["code"].upper() for entry in json.loads(path.read_text())]


def load_holding_currencies(catalog_paths: Iterable[Path]) -> dict[str, list[str]]:
    """Map each normalized holding currency to the sorted tickers priced in
    it, across every `catalog/<asset_class>.parquet` in `catalog_paths`.
    Tickers with no currency on record are skipped."""
    tickers_by_currency: dict[str, set[str]] = defaultdict(set)
    for path in catalog_paths:
        for row in pq.read_table(path, columns=["ticker", "currency"]).to_pylist():
            raw = row.get("currency")
            if not raw:
                continue
            currency = _CURRENCY_ALIASES.get(raw, raw)
            if not _ISO_CURRENCY.match(currency):
                logger.warning(
                    "Skipping %s: currency %r isn't a 3-letter ISO code", row["ticker"], raw
                )
                continue
            tickers_by_currency[currency].add(row["ticker"])
    return {currency: sorted(tickers) for currency, tickers in tickers_by_currency.items()}


def find_missing_pairs(
    holding_currencies: dict[str, list[str]],
    ui_currencies: list[str],
    configured: list[FxPair],
) -> list[dict[str, Any]]:
    """Every directed pair between a holding currency and a (different) UI
    currency, in either direction, that isn't in `configured` - sorted by
    `(from, to)`, each with the sorted tickers that need it."""
    configured_keys = {pair_key(p.from_currency, p.to_currency) for p in configured}
    needed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for currency, tickers in holding_currencies.items():
        for ui_currency in ui_currencies:
            if ui_currency == currency:
                continue
            for from_currency, to_currency in ((currency, ui_currency), (ui_currency, currency)):
                if pair_key(from_currency, to_currency) not in configured_keys:
                    needed[(from_currency, to_currency)].update(tickers)
    return [
        {"from": from_currency, "to": to_currency, "tickers": sorted(tickers)}
        for (from_currency, to_currency), tickers in sorted(needed.items())
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find FX pairs the given catalogs' holding currencies need but the FX "
        "config doesn't have."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        action="append",
        required=True,
        help="Path to a catalog/<asset_class>.parquet file (repeatable).",
    )
    parser.add_argument(
        "--fx-config", type=Path, required=True, help="Path to fx_pairs.<env>.yaml."
    )
    parser.add_argument(
        "--ui-currencies",
        type=Path,
        required=True,
        help="Path to frontend/src/config/currencies.json.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    configured = load_fx_pairs(args.fx_config)
    missing = find_missing_pairs(
        load_holding_currencies(args.catalog),
        load_ui_currencies(args.ui_currencies),
        configured,
    )
    print(
        json.dumps(
            {
                "missing": missing,
                "configured": sorted(pair_key(p.from_currency, p.to_currency) for p in configured),
            }
        )
    )


if __name__ == "__main__":
    main()
