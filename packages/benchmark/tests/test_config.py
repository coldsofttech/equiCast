from pathlib import Path

from equicast_benchmark.config import Benchmark, load_benchmarks, parse_benchmarks_json


def test_load_benchmarks(tmp_path: Path) -> None:
    config = tmp_path / "benchmarks.yaml"
    config.write_text(
        """
        benchmarks:
          - key: sp500
            symbol: "^GSPC"
          - key: ftse100
            symbol: "^FTSE"
        """
    )

    benchmarks = load_benchmarks(config)

    assert benchmarks == [
        Benchmark(key="SP500", symbol="^GSPC"),
        Benchmark(key="FTSE100", symbol="^FTSE"),
    ]


def test_parse_benchmarks_json() -> None:
    benchmarks = parse_benchmarks_json(
        '[{"key": "sp500", "symbol": "^GSPC"}, {"key": "dax", "symbol": "^GDAXI"}]'
    )

    assert benchmarks == [
        Benchmark(key="SP500", symbol="^GSPC"),
        Benchmark(key="DAX", symbol="^GDAXI"),
    ]
