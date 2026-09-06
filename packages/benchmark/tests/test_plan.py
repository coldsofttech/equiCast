import json
from pathlib import Path

import pytest
from equicast_benchmark.config import Benchmark
from equicast_benchmark.plan import chunk_benchmarks


def _benchmarks(n: int) -> list[Benchmark]:
    return [Benchmark(key=f"B{i:04d}", symbol=f"^B{i:04d}") for i in range(n)]


def test_chunk_benchmarks_respects_chunk_size_when_under_max_chunks() -> None:
    chunks = chunk_benchmarks(_benchmarks(10), chunk_size=4, max_chunks=256)

    assert [len(c) for c in chunks] == [4, 4, 2]


def test_chunk_benchmarks_grows_chunk_size_to_respect_max_chunks() -> None:
    # 3000 benchmarks at chunk_size=1 would need 3000 chunks; GitHub's matrix
    # cap forces a larger effective chunk size instead of dropping benchmarks.
    chunks = chunk_benchmarks(_benchmarks(3000), chunk_size=1, max_chunks=256)

    assert len(chunks) <= 256
    assert sum(len(c) for c in chunks) == 3000


def test_chunk_benchmarks_empty_input_returns_no_chunks() -> None:
    assert chunk_benchmarks([], chunk_size=300, max_chunks=256) == []


def test_chunk_benchmarks_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        chunk_benchmarks(_benchmarks(1), chunk_size=0, max_chunks=256)
    with pytest.raises(ValueError):
        chunk_benchmarks(_benchmarks(1), chunk_size=1, max_chunks=0)


def test_plan_cli_prints_json_chunks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from equicast_benchmark.plan import main

    config = tmp_path / "benchmarks.yaml"
    config.write_text(
        'benchmarks:\n  - key: SP500\n    symbol: "^GSPC"\n  - key: DAX\n    symbol: "^GDAXI"\n'
    )

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-benchmark-plan", "--config", str(config), "--chunk-size", "1"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [
        [{"key": "SP500", "symbol": "^GSPC"}],
        [{"key": "DAX", "symbol": "^GDAXI"}],
    ]
