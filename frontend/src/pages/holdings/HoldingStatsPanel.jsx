import { useState } from "react";
import Card from "../../components/core/Card.jsx";
import Button from "../../components/core/Button.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import FieldList from "../../components/core/FieldList.jsx";
import {
  buildPlaceholderMetrics,
  extractPriceWindow,
  formatCurrency,
  formatPrice,
} from "./holdingFinancials.js";

/**
 * A vertical high/low range bar — see .temp/52week_1week chart.png, the
 * design this mirrors, extended so the 1 Day and 52 Weeks bars are
 * directly comparable: both draw against the same `overallHigh`/
 * `overallLow` track (the min low and max high across *both* windows), so
 * a given price level sits at the same vertical position in either bar.
 * The grey track is that shared range; the colored segment on top of it is
 * this column's own high/low sub-range within that track, colored green
 * when this window's trading was net positive (close >= open) and red
 * when net negative — `trend` is `null` when open/close aren't both known,
 * in which case it defaults to green rather than leaving the segment
 * uncolored. A pointer marks where the current price sits on the shared
 * track. Renders nothing if the shared range can't be computed.
 */
function RangeBar({ overallHigh, overallLow, high, low, trend, current }) {
  if (overallHigh == null || overallLow == null || high == null || low == null) return null;
  const span = overallHigh - overallLow || 1;

  const segmentTopPct = ((overallHigh - high) / span) * 100;
  const segmentBottomPct = ((overallHigh - low) / span) * 100;
  const segmentHeightPct = Math.max(segmentBottomPct - segmentTopPct, 4);

  const clampedCurrent = current != null ? Math.min(overallHigh, Math.max(overallLow, current)) : null;
  const pointerPct = clampedCurrent != null ? ((overallHigh - clampedCurrent) / span) * 100 : null;

  return (
    <div className="ec-holding-range-bar-wrap">
      <div className="ec-holding-range-bar-track" />
      <div
        className={`ec-holding-range-bar-segment ${trend === "down" ? "is-down" : "is-up"}`}
        style={{ top: `${segmentTopPct}%`, height: `${segmentHeightPct}%` }}
      />
      {pointerPct != null && (
        <div className="ec-holding-range-pointer" style={{ top: `${pointerPct}%` }} />
      )}
    </div>
  );
}

/** `high`/`low` are already resolved by the caller (real day/year profile
 * fields, or a price-history window); `overallHigh`/`overallLow` are the
 * shared track both columns draw their bar against (see RangeBar). */
function HighLowColumn({ title, high, low, overallHigh, overallLow, trend, currency, currentPrice }) {
  if (high == null && low == null) {
    return (
      <div className="ec-holding-range-col">
        <h4 className="ec-holding-range-title">{title}</h4>
        <p className="ec-chart-caption">Price history unavailable for this ticker.</p>
      </div>
    );
  }

  return (
    <div className="ec-holding-range-col">
      <h4 className="ec-holding-range-title">{title}</h4>
      <div className="ec-holding-range">
        <div className="ec-holding-range-info">
          <span className="ec-holding-range-label">High</span>
          <span className="ec-holding-range-value">{high != null ? formatPrice(high, currency) : "—"}</span>
        </div>
        <RangeBar
          overallHigh={overallHigh}
          overallLow={overallLow}
          high={high}
          low={low}
          trend={trend}
          current={currentPrice}
        />
        <div className="ec-holding-range-info">
          <span className="ec-holding-range-label">Low</span>
          <span className="ec-holding-range-value">{low != null ? formatPrice(low, currency) : "—"}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * The Stats card — see .temp/52week_1week chart.png for the design this
 * follows: a 1 Day / 52 Weeks high-low range side by side (a vertical bar
 * with a pointer marking the current price's position). 1 Day comes
 * straight off the profile's real day_high/day_low — there's no "1 week"
 * figure anywhere in the data (the profile only has day- and year-prefixed
 * fields), so this uses the day range instead rather than falling back to a full
 * year's range and mislabeling it. 52 Weeks uses the current calendar
 * year's published price history when there's enough of it, falling back
 * to the profile's year-to-date high/low early in the year before much of
 * it is published yet. Below that, a stacked metrics list
 * mixing real profile fields (market cap, dividend yield) with the four
 * seeded placeholders the backend doesn't expose yet (volatility, average
 * volume, P/E ratio, dividend frequency — see holdingFinancials.js's
 * buildPlaceholderMetrics), called out as sample data in the caption below
 * rather than per-row, to match the mockup's clean row style. "See all"
 * opens a Drawer with the rest of the real profile fields.
 *
 * @param {{ ticker: string, marketProfile: import("../../api/market.js").MarketProfile|null, priceResults: import("../../api/market.js").PriceRecord[]|null }} props
 */
function HoldingStatsPanel({ ticker, marketProfile, priceResults }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const fiftyTwoWeeks = extractPriceWindow(priceResults, priceResults?.length ?? 0);
  const fiftyTwoWeeksHigh = fiftyTwoWeeks.sufficient ? fiftyTwoWeeks.high : marketProfile?.year_high;
  const fiftyTwoWeeksLow = fiftyTwoWeeks.sufficient ? fiftyTwoWeeks.low : marketProfile?.year_low;
  const placeholders = buildPlaceholderMetrics(ticker);
  const currency = marketProfile?.currency;
  const currentPrice = marketProfile?.day_close ?? marketProfile?.day_average ?? null;

  const dayHigh = marketProfile?.day_high;
  const dayLow = marketProfile?.day_low;
  const highs = [dayHigh, fiftyTwoWeeksHigh].filter((v) => v != null);
  const lows = [dayLow, fiftyTwoWeeksLow].filter((v) => v != null);
  const overallHigh = highs.length > 0 ? Math.max(...highs) : null;
  const overallLow = lows.length > 0 ? Math.min(...lows) : null;

  const dayTrend =
    marketProfile?.day_open != null && marketProfile?.day_close != null
      ? marketProfile.day_close >= marketProfile.day_open
        ? "up"
        : "down"
      : null;
  const yearTrend =
    marketProfile?.year_open != null && marketProfile?.year_close != null
      ? marketProfile.year_close >= marketProfile.year_open
        ? "up"
        : "down"
      : null;

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <div>
          <h3 className="ec-section-title">Stats</h3>
          <p className="ec-holding-stats-caption">
            This gives you some of the key information for {ticker}.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setIsDrawerOpen(true)}>
          See all
        </Button>
      </div>

      <div className="ec-holding-highlow-grid">
        <HighLowColumn
          title="1 Day"
          high={dayHigh}
          low={dayLow}
          overallHigh={overallHigh}
          overallLow={overallLow}
          trend={dayTrend}
          currency={currency}
          currentPrice={currentPrice}
        />
        <HighLowColumn
          title="52 Weeks"
          high={fiftyTwoWeeksHigh}
          low={fiftyTwoWeeksLow}
          overallHigh={overallHigh}
          overallLow={overallLow}
          trend={yearTrend}
          currency={currency}
          currentPrice={currentPrice}
        />
      </div>

      <FieldList
        items={[
          { label: "Volatility", value: `${placeholders.volatilityPct.toFixed(1)}%` },
          {
            label: "Market cap",
            value: marketProfile?.market_cap != null ? formatCurrency(marketProfile.market_cap, currency) : null,
          },
          { label: "Average volume", value: placeholders.avgVolume.toLocaleString() },
          { label: "P/E ratio", value: placeholders.peRatio.toFixed(1) },
          {
            label: "Dividend yield",
            value: marketProfile?.dividend_yield != null ? `${(marketProfile.dividend_yield * 100).toFixed(2)}%` : null,
          },
          { label: "Dividend frequency", value: placeholders.dividendFrequency },
        ]}
      />
      <p className="ec-chart-caption">
        Volatility, average volume, P/E ratio and dividend frequency are sample data — market cap
        and dividend yield are real.
      </p>

      <Drawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="All metrics">
        <FieldList
          items={[
            { label: "Beta", value: marketProfile?.beta },
            { label: "Payout ratio", value: marketProfile?.payout_ratio },
            {
              label: "Dividend rate",
              value:
                marketProfile?.dividend_rate != null
                  ? formatCurrency(marketProfile.dividend_rate, currency)
                  : null,
            },
            { label: "Day open", value: marketProfile?.day_open != null ? formatCurrency(marketProfile.day_open, currency) : null },
            { label: "Day high", value: marketProfile?.day_high != null ? formatCurrency(marketProfile.day_high, currency) : null },
            { label: "Day low", value: marketProfile?.day_low != null ? formatCurrency(marketProfile.day_low, currency) : null },
            { label: "Day close", value: marketProfile?.day_close != null ? formatCurrency(marketProfile.day_close, currency) : null },
            { label: "Day average", value: marketProfile?.day_average != null ? formatCurrency(marketProfile.day_average, currency) : null },
            { label: "Year open", value: marketProfile?.year_open != null ? formatCurrency(marketProfile.year_open, currency) : null },
            { label: "Year high", value: marketProfile?.year_high != null ? formatCurrency(marketProfile.year_high, currency) : null },
            { label: "Year low", value: marketProfile?.year_low != null ? formatCurrency(marketProfile.year_low, currency) : null },
            { label: "Year close", value: marketProfile?.year_close != null ? formatCurrency(marketProfile.year_close, currency) : null },
            { label: "Year average", value: marketProfile?.year_average != null ? formatCurrency(marketProfile.year_average, currency) : null },
            { label: "50-day moving average", value: marketProfile?.moving_average_50_days != null ? formatCurrency(marketProfile.moving_average_50_days, currency) : null },
            { label: "200-day moving average", value: marketProfile?.moving_average_200_days != null ? formatCurrency(marketProfile.moving_average_200_days, currency) : null },
          ]}
        />
      </Drawer>
    </Card>
  );
}

export default HoldingStatsPanel;
