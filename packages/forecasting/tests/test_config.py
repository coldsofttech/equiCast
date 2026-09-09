from pathlib import Path

from equicast_forecasting.config import (
    FxPairRef,
    load_fx_pairs,
    load_tickers,
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
