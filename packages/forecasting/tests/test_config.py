from pathlib import Path

from equicast_forecasting.config import (
    BenchmarkRef,
    FutureRef,
    FxPairRef,
    load_benchmarks,
    load_futures,
    load_fx_pairs,
    load_tickers,
    parse_benchmarks_json,
    parse_futures_json,
    parse_fx_pairs_json,
    parse_tickers_json,
)


def test_load_tickers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text(
        """
        tickers:
          - aapl
          - msft
        """
    )

    assert load_tickers(config) == ["AAPL", "MSFT"]


def test_parse_tickers_json() -> None:
    assert parse_tickers_json('["aapl", "msft"]') == ["AAPL", "MSFT"]


def test_load_fx_pairs(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text(
        """
        pairs:
          - from: gbp
            to: usd
          - from: eur
            to: gbp
        """
    )

    assert load_fx_pairs(config) == [
        FxPairRef(from_currency="GBP", to_currency="USD"),
        FxPairRef(from_currency="EUR", to_currency="GBP"),
    ]


def test_parse_fx_pairs_json() -> None:
    payload = '[{"from": "gbp", "to": "usd"}, {"from": "eur", "to": "gbp"}]'

    assert parse_fx_pairs_json(payload) == [
        FxPairRef(from_currency="GBP", to_currency="USD"),
        FxPairRef(from_currency="EUR", to_currency="GBP"),
    ]


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

    assert load_benchmarks(config) == [
        BenchmarkRef(key="SP500", symbol="^GSPC"),
        BenchmarkRef(key="FTSE100", symbol="^FTSE"),
    ]


def test_parse_benchmarks_json() -> None:
    payload = '[{"key": "sp500", "symbol": "^GSPC"}, {"key": "ftse100", "symbol": "^FTSE"}]'

    assert parse_benchmarks_json(payload) == [
        BenchmarkRef(key="SP500", symbol="^GSPC"),
        BenchmarkRef(key="FTSE100", symbol="^FTSE"),
    ]


def test_load_futures(tmp_path: Path) -> None:
    config = tmp_path / "futures.yaml"
    config.write_text(
        """
        futures:
          - key: gold
            symbol: "GC=F"
          - key: silver
            symbol: "SI=F"
        """
    )

    assert load_futures(config) == [
        FutureRef(key="GOLD", symbol="GC=F"),
        FutureRef(key="SILVER", symbol="SI=F"),
    ]


def test_parse_futures_json() -> None:
    payload = '[{"key": "gold", "symbol": "GC=F"}, {"key": "silver", "symbol": "SI=F"}]'

    assert parse_futures_json(payload) == [
        FutureRef(key="GOLD", symbol="GC=F"),
        FutureRef(key="SILVER", symbol="SI=F"),
    ]
