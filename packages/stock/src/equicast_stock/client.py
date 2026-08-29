"""Class-based client for a single stock ticker, backed by yfinance via equicast-datafeed."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient, round_value, warn_once

logger = logging.getLogger(__name__)

#: yfinance's own trailing 52-week window, reused as the "year" window for
#: year_open/year_high/year_low/year_close/year_average — same as equicast-fx.
YEAR_HISTORY_PERIOD = "1y"


def _midpoint(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return (low + high) / 2


#: Matches "CEO" (as a whole word, so it doesn't match inside e.g. "ceosome")
#: or "Chief Executive Officer" in an officer/executive title, case-insensitive
#: so it also picks up "Co-CEO", "President, CEO & Director", etc.
_CEO_TITLE_RE = re.compile(r"\bceo\b|chief executive officer", re.IGNORECASE)

#: A capitalized 2-4 word name (e.g. "Timothy D. Cook") immediately before or
#: after a CEO mention in free-text, e.g. "Timothy D. Cook serves as Chief
#: Executive Officer" or "Chief Executive Officer Timothy D. Cook". Names are
#: matched case-sensitively (real names are capitalized); the role phrase
#: itself is deliberately not case-insensitive here since business summaries
#: consistently capitalize it as a proper title/acronym.
_NAME = r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}"
_SUMMARY_CEO_RE = re.compile(
    rf"(?P<name_before>{_NAME})\s+(?:is|serves as|as)\s+(?:the\s+)?"
    rf"(?:Chief Executive Officer|CEO)"
    rf"|(?:Chief Executive Officer|CEO),?\s+(?P<name_after>{_NAME})"
)


def _ceos_from_people(people: list[dict[str, Any]]) -> list[dict[str, str]]:
    """{"name", "role"} entries for officers/executives whose title indicates
    CEO, from a companyOfficers/executiveTeam-shaped list of {"name",
    "title"} dicts. `role` is that person's actual title as reported (e.g.
    "Co-CEO", "Chairman, President and CEO"), not normalized to just "CEO".
    """
    return [
        {"name": person["name"], "role": person["title"]}
        for person in people
        if "name" in person and _CEO_TITLE_RE.search(person.get("title", ""))
    ]


def _ceos_from_summary(summary: str | None) -> list[dict[str, str]]:
    """{"name", "role"} entries pattern-matched from free-text.

    Unlike `_ceos_from_people`, there's no real title to report here — just
    a name found next to a CEO mention — so `role` is always the literal
    string "CEO" rather than an extracted phrase.
    """
    if not summary:
        return []
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _SUMMARY_CEO_RE.finditer(summary):
        name = match.group("name_before") or match.group("name_after")
        if name and name not in seen:
            seen.add(name)
            entries.append({"name": name, "role": "CEO"})
    return entries


def _ceos(info: dict[str, Any]) -> list[dict[str, str]]:
    """Best-effort CEO {"name", "role"} entries, tried in order of reliability.

    1. `companyOfficers` — structured, most reliable when present.
    2. `executiveTeam` — an alternate structured field yfinance populates
       for some tickers/versions when `companyOfficers` has no CEO entry.
    3. `longBusinessSummary` — free-text pattern match for a capitalized
       name next to a "CEO"/"Chief Executive Officer" mention, only tried
       when neither structured field yields a match. Prose is inherently
       harder to parse reliably than the officer/executive dicts, so this
       tier can occasionally miss a name or match nothing at all.
    """
    entries = _ceos_from_people(info.get("companyOfficers") or [])
    if entries:
        return entries

    entries = _ceos_from_people(info.get("executiveTeam") or [])
    if entries:
        return entries

    return _ceos_from_summary(info.get("longBusinessSummary"))


def _format_address(info: dict[str, Any]) -> str | None:
    """A single formatted mailing address string, e.g.
    "One Apple Park Way, Cupertino, CA 95014".

    Built from address1/address2/city/state/zip — distinct from the
    `country`/`region` profile fields, which come from yfinance's own
    `country`/`region` keys and are kept separate (not folded into this
    string) so they stay independently filterable.
    """
    state_zip = " ".join(str(part) for part in (info.get("state"), info.get("zip")) if part)
    parts: list[str] = [
        str(part)
        for part in (info.get("address1"), info.get("address2"), info.get("city"), state_zip)
        if part
    ]
    return ", ".join(parts) if parts else None


def _ipo_date(info: dict[str, Any]) -> str | None:
    """Best-effort IPO date, in the same ISO 8601 datetime format as `last_updated`.

    yfinance has no true IPO date field. `firstTradeDateMilliseconds` is the
    first date yfinance itself has trading data for this ticker, which can
    differ from the actual IPO date (data-vendor cutoffs, relistings,
    spin-offs) — falls back to `firstTradeDateEpochUtc` (seconds, seen on
    some tickers/yfinance versions) if the milliseconds field isn't present.
    """
    millis = info.get("firstTradeDateMilliseconds")
    if millis is not None:
        return datetime.fromtimestamp(millis / 1000, tz=UTC).isoformat()

    epoch_seconds = info.get("firstTradeDateEpochUtc")
    if epoch_seconds is not None:
        return datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat()

    return None


class StockClient:
    """Fetches profile data for one stock ticker."""

    def __init__(self, ticker: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, YFINANCE_DATA_DISCLAIMER)
        self.ticker = ticker.upper()
        self._datafeed = datafeed or DatafeedClient()

    @property
    def symbol(self) -> str:
        """The yfinance ticker symbol, e.g. `AAPL` (no suffix, unlike FX pairs)."""
        return self.ticker

    def profile(self) -> dict[str, Any]:
        """Return profile data for this stock ticker."""
        info = self._datafeed.get_info(self.symbol)
        history = self._datafeed.get_history(self.symbol, period=YEAR_HISTORY_PERIOD)

        market_time = info.get("regularMarketTime")
        last_updated = (
            datetime.fromtimestamp(market_time, tz=UTC).isoformat()
            if market_time is not None
            else datetime.now(UTC).isoformat()
        )

        day_high = info.get("regularMarketDayHigh")
        day_low = info.get("regularMarketDayLow")
        day_close = info.get("regularMarketPrice")

        year_open = float(history["Open"].iloc[0]) if not history.empty else None
        year_high = info.get("fiftyTwoWeekHigh")
        year_low = info.get("fiftyTwoWeekLow")

        return {
            "ticker": self.ticker,
            "name": info.get("longName") or info.get("shortName"),
            "quote_type": info.get("quoteType"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "description": info.get("longBusinessSummary"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "beta": round_value(info.get("beta")),
            "payout_ratio": round_value(info.get("payoutRatio")),
            "dividend_rate": round_value(info.get("dividendRate")),
            "dividend_yield": round_value(info.get("dividendYield")),
            "market_cap": info.get("marketCap"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "day_open": round_value(info.get("regularMarketOpen")),
            "day_high": round_value(day_high),
            "day_low": round_value(day_low),
            "day_close": round_value(day_close),
            "day_average": round_value(_midpoint(day_low, day_high)),
            "year_open": round_value(year_open),
            "year_high": round_value(year_high),
            "year_low": round_value(year_low),
            "year_close": round_value(day_close),
            "year_average": round_value(_midpoint(year_low, year_high)),
            "moving_average_50_days": round_value(info.get("fiftyDayAverage")),
            "moving_average_200_days": round_value(info.get("twoHundredDayAverage")),
            "address": _format_address(info),
            "country": info.get("country"),
            "region": info.get("region"),
            "full_time_employees": info.get("fullTimeEmployees"),
            "ceos": _ceos(info),
            "ipo_date": _ipo_date(info),
            "last_updated": last_updated,
            "source": "yfinance",
        }
