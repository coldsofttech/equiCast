import json
from pathlib import Path

import pytest
from equicast_stock.config import StockTicker
from equicast_stock.plan import _serialize_ticker, chunk_tickers, filter_tickers


def _tickers(n: int) -> list[StockTicker]:
    return [StockTicker(ticker=f"T{i:04d}") for i in range(n)]


def test_chunk_tickers_respects_chunk_size_when_under_max_chunks() -> None:
    chunks = chunk_tickers(_tickers(10), chunk_size=4, max_chunks=256)

    assert [len(c) for c in chunks] == [4, 4, 2]


def test_chunk_tickers_grows_chunk_size_to_respect_max_chunks() -> None:
    # 3000 tickers at chunk_size=1 would need 3000 chunks; GitHub's matrix
    # cap forces a larger effective chunk size instead of dropping tickers.
    chunks = chunk_tickers(_tickers(3000), chunk_size=1, max_chunks=256)

    assert len(chunks) <= 256
    assert sum(len(c) for c in chunks) == 3000


def test_chunk_tickers_empty_input_returns_no_chunks() -> None:
    assert chunk_tickers([], chunk_size=300, max_chunks=256) == []


def test_chunk_tickers_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        chunk_tickers(_tickers(1), chunk_size=0, max_chunks=256)
    with pytest.raises(ValueError):
        chunk_tickers(_tickers(1), chunk_size=1, max_chunks=0)


def test_filter_tickers_returns_unchanged_when_keys_is_none() -> None:
    tickers = _tickers(3)
    assert filter_tickers(tickers, None) == tickers


def test_filter_tickers_returns_unchanged_when_keys_is_empty_string() -> None:
    tickers = _tickers(3)
    assert filter_tickers(tickers, "") == tickers


def test_filter_tickers_restricts_to_matching_keys() -> None:
    tickers = [StockTicker(ticker="AAPL"), StockTicker(ticker="MSFT"), StockTicker(ticker="NWG.L")]

    assert [t.ticker for t in filter_tickers(tickers, "MSFT;NWG.L")] == ["MSFT", "NWG.L"]


def test_filter_tickers_is_case_insensitive_and_ignores_blank_entries() -> None:
    tickers = [StockTicker(ticker="AAPL"), StockTicker(ticker="MSFT")]

    assert [t.ticker for t in filter_tickers(tickers, " aapl ; ;msft ")] == ["AAPL", "MSFT"]


def test_filter_tickers_drops_unmatched_keys() -> None:
    tickers = [StockTicker(ticker="AAPL")]

    assert filter_tickers(tickers, "NOPE") == []


def test_serialize_ticker_plain_when_no_overrides() -> None:
    assert _serialize_ticker(StockTicker(ticker="AAPL")) == "AAPL"


def test_serialize_ticker_with_isin_override_only() -> None:
    assert _serialize_ticker(StockTicker(ticker="STX", isin="IE00BKVD2N49")) == {
        "ticker": "STX",
        "isin": "IE00BKVD2N49",
    }


def test_serialize_ticker_with_tax_domicile_override_only() -> None:
    assert _serialize_ticker(StockTicker(ticker="AAPL", tax_domicile="US")) == {
        "ticker": "AAPL",
        "tax_domicile": "US",
    }


def test_serialize_ticker_with_both_overrides() -> None:
    assert _serialize_ticker(
        StockTicker(ticker="MSFT", isin="US5949181045", tax_domicile="US")
    ) == {
        "ticker": "MSFT",
        "isin": "US5949181045",
        "tax_domicile": "US",
    }


def test_plan_cli_prints_json_chunks_preserves_isin_and_tax_domicile_overrides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from equicast_stock.plan import main

    config = tmp_path / "stocks.yaml"
    config.write_text(
        "tickers:\n"
        "  - AAPL\n"
        "  - ticker: MSFT\n"
        "    isin: US5949181045\n"
        "    tax_domicile: US\n"
    )

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-stock-plan", "--config", str(config), "--chunk-size", "2"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [["AAPL", {"ticker": "MSFT", "isin": "US5949181045", "tax_domicile": "US"}]]


def test_plan_cli_prints_json_chunks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from equicast_stock.plan import main

    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-stock-plan", "--config", str(config), "--chunk-size", "1"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [["AAPL"], ["MSFT"]]


def test_plan_cli_restricts_to_given_tickers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from equicast_stock.plan import main

    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n  - NWG.L\n")

    import sys

    old_argv = sys.argv
    sys.argv = [
        "equicast-stock-plan",
        "--config",
        str(config),
        "--chunk-size",
        "300",
        "--tickers",
        "MSFT;NWG.L",
    ]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [["MSFT", "NWG.L"]]
