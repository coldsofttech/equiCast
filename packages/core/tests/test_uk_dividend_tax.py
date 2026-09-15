import pytest
from equicast_core.uk_dividend_tax import compute_uk_dividend_tax, uk_tax_year_label


@pytest.mark.parametrize(
    "iso_date,expected",
    [
        ("2026-04-06", "2026-27"),  # first day of the 2026-27 tax year
        ("2026-09-15", "2026-27"),
        ("2027-04-05", "2026-27"),  # last day of the 2026-27 tax year
        ("2027-04-06", "2027-28"),  # first day of the next tax year
        ("2026-01-01", "2025-26"),  # before 6 Apr -> previous tax year
    ],
)
def test_uk_tax_year_label(iso_date: str, expected: str) -> None:
    assert uk_tax_year_label(iso_date) == expected


@pytest.mark.parametrize("wrapper_type", ["ISA", "SIPP", "LISA", "JISA"])
def test_exempt_wrapper_types_pay_zero_tax_and_consume_no_allowance(wrapper_type: str) -> None:
    result = compute_uk_dividend_tax(
        wrapper_type=wrapper_type,
        tax_domicile="US",
        default_withholding_pct=15.0,
        tax_override_pct=None,
        income_tax_band="ADDITIONAL",
        gross_amount=1000.0,
        allowance_used_ytd=0.0,
    )

    assert result["wrapper_taxable"] is False
    assert result["tax_amount"] == 0.0
    assert result["net_amount"] == 1000.0
    assert result["allowance_consumed"] == 0.0
    assert result["new_allowance_used_ytd"] == 0.0


def test_gia_uk_holding_crossing_the_allowance_threshold() -> None:
    # £480 of the £500 allowance already used this tax year; this £100 UK
    # dividend uses the remaining £20, then taxes the other £80 at BASIC.
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile="UK",
        default_withholding_pct=None,
        tax_override_pct=None,
        income_tax_band="BASIC",
        gross_amount=100.0,
        allowance_used_ytd=480.0,
    )

    assert result["wrapper_taxable"] is True
    assert result["withholding_pct_applied"] == 0.0
    assert result["net_of_withholding"] == 100.0
    assert result["allowance_consumed"] == 20.0
    assert result["taxable_amount"] == 80.0
    assert result["tax_rate_applied"] == pytest.approx(0.0875)
    assert result["tax_amount"] == pytest.approx(7.0)
    assert result["net_amount"] == pytest.approx(93.0)
    assert result["new_allowance_used_ytd"] == 500.0


def test_gia_foreign_holding_applies_withholding_then_uk_tax() -> None:
    # US-domiciled, 15% withholding, no allowance left, HIGHER band.
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile="US",
        default_withholding_pct=15.0,
        tax_override_pct=None,
        income_tax_band="HIGHER",
        gross_amount=100.0,
        allowance_used_ytd=500.0,
    )

    assert result["withholding_pct_applied"] == 15.0
    assert result["withholding_amount"] == pytest.approx(15.0)
    assert result["net_of_withholding"] == pytest.approx(85.0)
    assert result["allowance_consumed"] == 0.0
    assert result["taxable_amount"] == pytest.approx(85.0)
    assert result["tax_rate_applied"] == pytest.approx(0.3375)
    assert result["tax_amount"] == pytest.approx(28.6875)
    assert result["net_amount"] == pytest.approx(56.3125)
    assert result["new_allowance_used_ytd"] == 500.0


def test_tax_override_pct_takes_precedence_over_domicile_withholding() -> None:
    # No W-8BEN on file for this account -> real US withholding is 30%, not
    # the domicile-derived 15% default.
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile="US",
        default_withholding_pct=15.0,
        tax_override_pct=30.0,
        income_tax_band="BASIC",
        gross_amount=100.0,
        allowance_used_ytd=0.0,
    )

    assert result["withholding_pct_applied"] == 30.0
    assert result["net_of_withholding"] == pytest.approx(70.0)


def test_tax_override_pct_applies_even_for_a_uk_domiciled_holding() -> None:
    # Override wins outright, regardless of what the domicile check would
    # otherwise conclude (UK domicile normally means 0% withholding).
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile="UK",
        default_withholding_pct=None,
        tax_override_pct=10.0,
        income_tax_band="BASIC",
        gross_amount=100.0,
        allowance_used_ytd=0.0,
    )

    assert result["withholding_pct_applied"] == 10.0
    assert result["net_of_withholding"] == pytest.approx(90.0)


def test_gia_none_income_tax_band_stays_untaxed_but_still_consumes_allowance() -> None:
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile="UK",
        default_withholding_pct=None,
        tax_override_pct=None,
        income_tax_band="NONE",
        gross_amount=600.0,
        allowance_used_ytd=0.0,
    )

    assert result["allowance_consumed"] == 500.0
    assert result["taxable_amount"] == 100.0
    assert result["tax_amount"] == 0.0
    assert result["net_amount"] == 600.0
    assert result["new_allowance_used_ytd"] == 500.0


def test_gia_unknown_domicile_without_override_applies_no_withholding() -> None:
    result = compute_uk_dividend_tax(
        wrapper_type="GIA",
        tax_domicile=None,
        default_withholding_pct=None,
        tax_override_pct=None,
        income_tax_band="BASIC",
        gross_amount=100.0,
        allowance_used_ytd=0.0,
    )

    assert result["withholding_pct_applied"] == 0.0
    assert result["net_of_withholding"] == 100.0
