import pytest
from equicast_forecasting.benchmark_registry import (
    BENCHMARK_SCHEMAS,
    UnroutableBenchmarkError,
    route_benchmark,
)

#: Every benchmark currently configured in
#: packages/benchmark/config/benchmarks.prod.yaml needs its own explicit
#: entry here (no generic fallback) - see benchmark_schemas.yaml's header
#: comment for why.
CONFIGURED_KEYS = [
    "MSCI_WORLD",
    "MSCI_ACWI",
    "MSCI_EM",
    "SP500",
    "DOW_JONES",
    "NASDAQ100",
    "RUSSELL3000",
    "RUSSELL2000",
    "FTSE100",
    "FTSE250",
    "FTSE_ALL_SHARE",
    "STOXX_EUROPE_600",
    "EURO_STOXX_50",
    "DAX",
    "NIKKEI225",
]


@pytest.mark.parametrize("key", CONFIGURED_KEYS)
def test_route_benchmark_matches_every_configured_key(key: str) -> None:
    assert route_benchmark(key).key == key


def test_route_benchmark_is_case_insensitive() -> None:
    assert route_benchmark("sp500").key == "SP500"


def test_route_benchmark_raises_for_unknown_key() -> None:
    with pytest.raises(UnroutableBenchmarkError):
        route_benchmark("NOT_A_REAL_BENCHMARK")


def test_route_benchmark_raises_for_none_key() -> None:
    with pytest.raises(UnroutableBenchmarkError):
        route_benchmark(None)


def test_unroutable_benchmark_error_carries_key() -> None:
    try:
        route_benchmark("NOT_A_REAL_BENCHMARK")
    except UnroutableBenchmarkError as error:
        assert error.key == "NOT_A_REAL_BENCHMARK"
    else:
        pytest.fail("expected UnroutableBenchmarkError")


def test_every_configured_key_is_registered() -> None:
    assert {schema.key for schema in BENCHMARK_SCHEMAS} == set(CONFIGURED_KEYS)


def test_every_schema_declares_all_three_horizons() -> None:
    for schema in BENCHMARK_SCHEMAS:
        assert set(schema.parameters.keys()) == {"short", "medium", "long"}
        for horizon_params in schema.parameters.values():
            assert len(horizon_params) > 0


def test_every_schema_declares_a_currency_sensitivity() -> None:
    known = {"none", "low", "moderate", "high"}
    for schema in BENCHMARK_SCHEMAS:
        assert schema.currency_sensitivity in known


def test_ftse100_is_more_currency_sensitive_than_sp500() -> None:
    # The issue's own framing: "FTSE 100's heavy overseas-earnings
    # weighting means FX correlation matters more here than for S&P
    # 500/Russell 3000."
    sensitivity_rank = {"none": 0, "low": 1, "moderate": 2, "high": 3}
    ftse100 = sensitivity_rank[route_benchmark("FTSE100").currency_sensitivity]
    sp500 = sensitivity_rank[route_benchmark("SP500").currency_sensitivity]
    russell3000 = sensitivity_rank[route_benchmark("RUSSELL3000").currency_sensitivity]
    assert ftse100 > sp500
    assert ftse100 > russell3000
