"""Prints a comma-separated, sorted list of tickers with no ISIN on record
in a catalog/<asset_class>.parquet file (see equicast_core.catalog — the
catalog already carries each ticker's isin, so this reads that rather than
re-scanning every chunk's individual profile.parquet).

Used by stock-ingestion.yml/etf-ingestion.yml's build-catalog job to feed
sync-missing-isin-issue.sh, which opens/updates/closes a GitHub issue
listing the result (GitHub issue #215)."""

import argparse

import pyarrow.parquet as pq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog", required=True, help="Path to a local catalog/<asset_class>.parquet file."
    )
    args = parser.parse_args()

    rows = pq.read_table(args.catalog).to_pylist()
    missing = sorted(row["ticker"] for row in rows if not row.get("isin"))
    print(",".join(missing))


if __name__ == "__main__":
    main()
