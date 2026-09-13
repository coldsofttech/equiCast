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


def test_load_stock_tickers_with_isin_and_tax_domicile_overrides(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text(
        """
        tickers:
          - aapl
          - ticker: stx
            isin: IE00BKVD2N49
          - ticker: msft
            isin: US5949181045
            tax_domicile: US
        """
    )

    tickers = load_stock_tickers(config)

    assert tickers == [
        StockTicker(ticker="AAPL"),
        StockTicker(ticker="STX", isin="IE00BKVD2N49"),
        StockTicker(ticker="MSFT", isin="US5949181045", tax_domicile="US"),
    ]


def test_stock_ticker_key() -> None:
    assert StockTicker(ticker="AAPL").key == "AAPL"


def test_parse_stock_tickers_json() -> None:
    tickers = parse_stock_tickers_json('["aapl", "msft"]')

    assert tickers == [
        StockTicker(ticker="AAPL"),
        StockTicker(ticker="MSFT"),
    ]


def test_parse_stock_tickers_json_with_isin_and_tax_domicile_overrides() -> None:
    tickers = parse_stock_tickers_json(
        '[{"ticker": "msft", "isin": "US5949181045", "tax_domicile": "US"}]'
    )

    assert tickers == [StockTicker(ticker="MSFT", isin="US5949181045", tax_domicile="US")]
