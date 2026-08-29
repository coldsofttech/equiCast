from pathlib import Path

from equicast_fx.config import FxPair, load_fx_pairs, parse_fx_pairs_json


def test_load_fx_pairs(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text(
        """
        pairs:
          - from: gbp
            to: usd
          - from: usd
            to: gbp
        """
    )

    pairs = load_fx_pairs(config)

    assert pairs == [
        FxPair(from_currency="GBP", to_currency="USD"),
        FxPair(from_currency="USD", to_currency="GBP"),
    ]


def test_fx_pair_key() -> None:
    assert FxPair(from_currency="GBP", to_currency="USD").key == "GBPUSD"


def test_parse_fx_pairs_json() -> None:
    pairs = parse_fx_pairs_json('[{"from": "gbp", "to": "usd"}, {"from": "eur", "to": "gbp"}]')

    assert pairs == [
        FxPair(from_currency="GBP", to_currency="USD"),
        FxPair(from_currency="EUR", to_currency="GBP"),
    ]
