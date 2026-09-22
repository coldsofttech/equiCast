"""Applies a human-provided ISIN (and optional tax_domicile) override to a
ticker's entry in its pipeline's <asset_class>.prod.yaml config, converting
a plain `- TICKER` list entry into a `{ticker, isin}` mapping (or updating
an existing mapping's isin) in place, editing only the lines involved so
the rest of the file's comments/formatting are untouched.

Cross-checks the ticker against every known *.prod.yaml (not just the one
named by the caller) so a stale/mismatched config path on the triggering
issue fails loudly instead of silently editing the wrong file. Used by
issue-automation-fix.yml's missing-isin-provided case (GitHub issue
equicast-support#149) once a maintainer replies to a "<TICKER>: missing
ISIN" sub-issue with the ISIN.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

KNOWN_CONFIGS = [
    "packages/stock/config/stocks.prod.yaml",
    "packages/etf/config/etfs.prod.yaml",
]


def _find_owning_configs(repo_root: Path, ticker: str) -> list[str]:
    """Repo-relative paths (of KNOWN_CONFIGS) whose tickers: list already
    lists this ticker, plain or as an override mapping."""
    owning = []
    for rel_path in KNOWN_CONFIGS:
        data = yaml.safe_load((repo_root / rel_path).read_text())
        for entry in data["tickers"]:
            entry_ticker = entry if isinstance(entry, str) else entry.get("ticker")
            if entry_ticker and entry_ticker.upper() == ticker:
                owning.append(rel_path)
                break
    return owning


def _apply_override(text: str, ticker: str, isin: str, tax_domicile: str | None) -> str:
    lines = text.splitlines(keepends=True)
    plain_re = re.compile(rf"^(\s*)-\s*{re.escape(ticker)}\s*\r?\n?$", re.IGNORECASE)
    mapping_re = re.compile(rf"^(\s*)-\s*ticker:\s*{re.escape(ticker)}\s*\r?\n?$", re.IGNORECASE)

    for i, line in enumerate(lines):
        if plain_re.match(line):
            indent = plain_re.match(line).group(1)
            replacement = f"{indent}- ticker: {ticker}\n{indent}  isin: {isin}\n"
            if tax_domicile:
                replacement += f"{indent}  tax_domicile: {tax_domicile}\n"
            lines[i : i + 1] = [replacement]
            return "".join(lines)

        if mapping_re.match(line):
            indent = mapping_re.match(line).group(1)
            block_end = i + 1
            while block_end < len(lines) and lines[block_end].startswith(indent + "  "):
                block_end += 1
            block = [ln for ln in lines[i:block_end] if not re.match(r"^\s*isin:", ln)]
            block.insert(1, f"{indent}  isin: {isin}\n")
            if tax_domicile and not any(re.match(r"^\s*tax_domicile:", ln) for ln in block):
                block.append(f"{indent}  tax_domicile: {tax_domicile}\n")
            lines[i:block_end] = block
            return "".join(lines)

    raise ValueError(f"{ticker!r} not found as a tickers: list entry")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--tax-domicile", default=None)
    parser.add_argument(
        "--config-path",
        required=True,
        help="Config path named by the triggering issue, repo-relative.",
    )
    parser.add_argument("--repo-root", default=".", type=Path)
    args = parser.parse_args()

    ticker = args.ticker.upper()
    tax_domicile = args.tax_domicile or None
    repo_root = Path(args.repo_root)

    owning = _find_owning_configs(repo_root, ticker)
    if len(owning) == 0:
        sys.exit(
            f"error: {ticker!r} not found in any known config "
            f"({', '.join(KNOWN_CONFIGS)}) - can't tell where to add it"
        )
    if len(owning) > 1:
        sys.exit(
            f"error: {ticker!r} found in more than one config ({', '.join(owning)}) - ambiguous"
        )
    if owning[0] != args.config_path:
        sys.exit(
            f"error: {ticker!r} lives in {owning[0]!r}, not the issue's "
            f"{args.config_path!r} - refusing to guess"
        )

    target = repo_root / owning[0]
    original = target.read_text()
    updated = _apply_override(original, ticker, args.isin, tax_domicile)

    # Round-trip validation: refuse to write unless the edited file still
    # parses and now carries the expected isin, so a regex slip never lands
    # a corrupted config.
    parsed = yaml.safe_load(updated)
    match = next(
        (
            e
            for e in parsed["tickers"]
            if isinstance(e, dict) and e.get("ticker", "").upper() == ticker
        ),
        None,
    )
    if match is None or match.get("isin") != args.isin:
        sys.exit(
            f"error: post-edit validation failed for {ticker!r} in {owning[0]!r} - not writing"
        )

    target.write_text(updated)
    print(owning[0])


if __name__ == "__main__":
    main()
