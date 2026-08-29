from pathlib import Path

from equicast_stock.config import StockTicker, load_stock_tickers, parse_stock_tickers_json


def test_load_stock_tickers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text(
        """
        tickers:
          - aapl
          - msft
        """
    )

    tickers = load_stock_tickers(config)

    assert tickers == [
        StockTicker(ticker="AAPL"),
        StockTicker(ticker="MSFT"),
    ]


def test_stock_ticker_key() -> None:
    assert StockTicker(ticker="AAPL").key == "AAPL"


def test_parse_stock_tickers_json() -> None:
    tickers = parse_stock_tickers_json('["aapl", "msft"]')

    assert tickers == [
        StockTicker(ticker="AAPL"),
        StockTicker(ticker="MSFT"),
    ]
