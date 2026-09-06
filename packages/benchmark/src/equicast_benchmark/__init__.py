"""equicast-benchmark: class-based benchmark (market index) data extraction."""

from equicast_benchmark.client import BenchmarkClient
from equicast_benchmark.config import Benchmark, load_benchmarks, parse_benchmarks_json

__version__ = "0.1.0"

__all__ = ["BenchmarkClient", "Benchmark", "load_benchmarks", "parse_benchmarks_json"]
