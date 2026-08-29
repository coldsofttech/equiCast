from equicast_datafeed.rounding import DECIMAL_PRECISION, round_value


def test_round_value_rounds_to_default_precision() -> None:
    assert round_value(1.3504753112792969) == round(1.3504753112792969, DECIMAL_PRECISION)


def test_round_value_passes_none_through() -> None:
    assert round_value(None) is None


def test_round_value_accepts_custom_precision() -> None:
    assert round_value(1.23456789, precision=2) == 1.23
