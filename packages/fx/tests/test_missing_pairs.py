import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equicast_fx.config import FxPair
from equicast_fx.missing_pairs import (
    find_missing_pairs,
    load_holding_currencies,
    load_ui_currencies,
    main,
)


def _catalog(path: Path, rows: list[dict[str, str | None]]) -> Path:
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def _pair(from_currency: str, to_currency: str) -> FxPair:
    return FxPair(from_currency=from_currency, to_currency=to_currency)


def test_find_missing_pairs_requires_both_directions() -> None:
    missing = find_missing_pairs(
        {"USD": ["AAPL"]}, ["GBP", "USD"], configured=[_pair("USD", "GBP")]
    )

    assert missing == [{"from": "GBP", "to": "USD", "tickers": ["AAPL"]}]


def test_find_missing_pairs_nothing_missing_when_both_directions_configured() -> None:
    configured = [_pair("USD", "GBP"), _pair("GBP", "USD")]

    assert find_missing_pairs({"USD": ["AAPL"]}, ["GBP", "USD"], configured) == []


def test_find_missing_pairs_skips_same_currency() -> None:
    assert find_missing_pairs({"GBP": ["NWG.L"]}, ["GBP"], configured=[]) == []


def test_find_missing_pairs_one_entry_per_directed_pair_sorted() -> None:
    missing = find_missing_pairs({"JPY": ["7203.T"]}, ["GBP", "USD"], configured=[])

    assert [(m["from"], m["to"]) for m in missing] == [
        ("GBP", "JPY"),
        ("JPY", "GBP"),
        ("JPY", "USD"),
        ("USD", "JPY"),
    ]


def test_find_missing_pairs_merges_tickers_needing_the_same_pair() -> None:
    # A holding currency that is itself a UI currency needs the same pair a
    # UI currency needs back to it - both holdings' tickers are listed once.
    missing = find_missing_pairs(
        {"USD": ["AAPL"], "EUR": ["SAP.DE"]}, ["USD", "EUR"], configured=[]
    )

    assert missing == [
        {"from": "EUR", "to": "USD", "tickers": ["AAPL", "SAP.DE"]},
        {"from": "USD", "to": "EUR", "tickers": ["AAPL", "SAP.DE"]},
    ]


def test_load_holding_currencies_normalizes_pence_and_skips_unusable(tmp_path: Path) -> None:
    catalog = _catalog(
        tmp_path / "stock.parquet",
        [
            {"ticker": "NWG.L", "currency": "GBp"},
            {"ticker": "BARC.L", "currency": "GBP"},
            {"ticker": "AAPL", "currency": "USD"},
            {"ticker": "NPN.JO", "currency": "ZAc"},
            {"ticker": "NONE", "currency": None},
        ],
    )

    assert load_holding_currencies([catalog]) == {"GBP": ["BARC.L", "NWG.L"], "USD": ["AAPL"]}


def test_load_holding_currencies_merges_multiple_catalogs(tmp_path: Path) -> None:
    stock = _catalog(tmp_path / "stock.parquet", [{"ticker": "AAPL", "currency": "USD"}])
    etf = _catalog(tmp_path / "etf.parquet", [{"ticker": "VOO", "currency": "USD"}])

    assert load_holding_currencies([stock, etf]) == {"USD": ["AAPL", "VOO"]}


def test_load_ui_currencies(tmp_path: Path) -> None:
    path = tmp_path / "currencies.json"
    path.write_text(json.dumps([{"code": "GBP", "name": "British Pound"}, {"code": "usd"}]))

    assert load_ui_currencies(path) == ["GBP", "USD"]


def test_main_prints_missing_and_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = _catalog(tmp_path / "etf.parquet", [{"ticker": "VOO", "currency": "USD"}])
    fx_config = tmp_path / "fx.yaml"
    fx_config.write_text("pairs:\n  - from: USD\n    to: GBP\n")
    ui = tmp_path / "currencies.json"
    ui.write_text(json.dumps([{"code": "GBP"}, {"code": "USD"}]))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "equicast-fx-find-missing-pairs",
            "--catalog",
            str(catalog),
            "--fx-config",
            str(fx_config),
            "--ui-currencies",
            str(ui),
        ],
    )

    main()

    assert json.loads(capsys.readouterr().out) == {
        "missing": [{"from": "GBP", "to": "USD", "tickers": ["VOO"]}],
        "configured": ["USD:GBP"],
    }
