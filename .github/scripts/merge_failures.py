"""Merges every ingest chunk's failures-<index>.json (see
equicast_stock/etf/fx/benchmark's writer.write_failures_manifest, written
whenever cli.run() catches an individual ticker/pair/benchmark task
failure - GitHub issue equicast-support#145) into a single JSON array,
printed to stdout.

Used by each ingestion workflow's report-status job, after downloading
every chunk's <pipeline>-profiles-* artifact (merge-multiple: true) into one
directory, to feed sync-pipeline-failure-subissues.sh a single run-wide
failures list rather than one file per chunk. Each chunk's failures.json is
renamed to failures-<job-index>.json before upload specifically so this
merge step can tell them apart after merge-multiple's same-path collision
would otherwise silently drop all but one chunk's failures.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory every chunk's failures-<index>.json was downloaded into.",
    )
    args = parser.parse_args()

    failures: list[dict[str, str]] = []
    for path in sorted(args.output_dir.glob("failures-*.json")):
        failures.extend(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps(failures))


if __name__ == "__main__":
    main()
