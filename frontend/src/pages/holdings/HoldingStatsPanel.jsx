import { useState } from "react";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import FieldList from "../../components/core/FieldList.jsx";
import {
  formatCompactCurrency,
  formatCurrency,
  formatDividendFrequency,
  formatPercent,
  formatPrice,
  formatRatio,
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
 * The "See all" Drawer's remaining metrics, grouped logically by subject —
 * everything `GET .../metrics/` returns (see market.js's MarketMetrics)
 * that isn't already in the main list (Volatility/P/E ratio are covered
 * there — the plain price/EPS `pe_ratio`, not `trailing_pe`, see the
 * component docstring below). `cagr_*` is deliberately excluded —
 * where/how to surface it is still to be decided. Each group renders as
 * its own FieldList so a group with nothing resolved (e.g. every
 * Valuation/Per-share/Profitability/Leverage field for an etf/fx ticker,
 * which has no fundamentals at all) can be hidden entirely rather than
 * showing an empty heading.
 *
 * @param {import("../../api/market.js").MarketMetrics|null} metrics
 * @param {string|null|undefined} currency
 * @returns {{ title: string, items: { label: string, value: string|null }[] }[]}
 */
function remainingMetricGroups(metrics, currency) {
  return [
    {
      title: "Valuation",
      items: [
        // pe_ratio (the plain price/EPS calculation) is the main list's
        // "P/E ratio" row — trailing_pe (yfinance's own reported figure,
        // which can disagree with the plain calculation) lives here instead.
        { label: "Trailing P/E", value: formatRatio(metrics?.trailing_pe) },
        { label: "Forward P/E", value: formatRatio(metrics?.forward_pe) },
        { label: "PEG ratio", value: formatRatio(metrics?.peg) },
        { label: "Price/Book", value: formatRatio(metrics?.price_to_book) },
        { label: "Price/Sales", value: formatRatio(metrics?.price_to_sales) },
        { label: "EV/EBITDA", value: formatRatio(metrics?.ev_ebitda) },
      ],
    },
    {
      title: "Per share",
      items: [
        { label: "Trailing EPS", value: metrics?.trailing_eps != null ? formatPrice(metrics.trailing_eps, currency) : null },
        { label: "Forward EPS", value: metrics?.forward_eps != null ? formatPrice(metrics.forward_eps, currency) : null },
        {
          label: "Free cash flow/share",
          value: metrics?.free_cash_flow_per_share != null
            ? formatPrice(metrics.free_cash_flow_per_share, currency)
            : null,
        },
      ],
    },
    {
      title: "Profitability",
      items: [
        { label: "Gross margin", value: formatPercent(metrics?.gross_margin) },
        { label: "Operating margin", value: formatPercent(metrics?.operating_margin) },
        { label: "Profit margin", value: formatPercent(metrics?.profit_margin) },
        { label: "Return on equity", value: formatPercent(metrics?.return_on_equity) },
        { label: "Return on assets", value: formatPercent(metrics?.return_on_assets) },
      ],
    },
    {
      title: "Leverage",
      items: [
        // debt_to_equity is already a percentage (e.g. 150.0 == 150%), not
        // a fraction — see equicast_metrics.fundamentals' own comment on it.
        { label: "Debt/Equity", value: metrics?.debt_to_equity != null ? `${metrics.debt_to_equity.toFixed(1)}%` : null },
      ],
    },
    {
      title: "Risk",
      items: [
        { label: "Sharpe ratio", value: formatRatio(metrics?.sharpe_ratio) },
        { label: "Max drawdown", value: formatPercent(metrics?.max_drawdown) },
      ],
    },
  ];
}

/**
 * The Stats card — see .temp/52week_1week chart.png for the design this
 * follows: a 1 Day / 52 Weeks high-low range side by side (a vertical bar
 * with a pointer marking the current price's position). 1 Day comes
 * straight off the profile's real day_high/day_low — there's no "1 week"
 * figure anywhere in the data (the profile only has day- and year-prefixed
 * fields), so this uses the day range instead rather than falling back to a full
 * year's range and mislabeling it. 52 Weeks comes straight off the
 * profile's own year_high/year_low. Below that, a stacked metrics list
 * mixing real profile fields (market cap, dividend yield, beta, payout
 * ratio, dividend rate, dividend frequency — see holdingFinancials.js's
 * formatDividendFrequency) with real risk/valuation fields off `GET
 * .../metrics/` (Volatility, and P/E ratio — `pe_ratio`, the plain price ÷
 * trailing EPS calculation, not `trailing_pe`, which prefers yfinance's own
 * reported figure and can disagree with the plain calculation; that one's
 * in the "See all" Valuation group instead). A "See all" link opens a
 * Drawer with every other metrics field, grouped by subject (see
 * remainingMetricGroups) — `cagr_*` is deliberately left out, its placement
 * is still to be decided.
 *
 * @param {{ marketProfile: import("../../api/market.js").MarketProfile|null, marketMetrics: import("../../api/market.js").MarketMetrics|null }} props
 */
function HoldingStatsPanel({ marketProfile, marketMetrics }) {
  const [isSeeAllOpen, setIsSeeAllOpen] = useState(false);

  const fiftyTwoWeeksHigh = marketProfile?.year_high ?? null;
  const fiftyTwoWeeksLow = marketProfile?.year_low ?? null;
  const currency = marketProfile?.currency;
  const currentPrice = marketProfile?.day_close ?? null;

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

  const metricGroups = remainingMetricGroups(marketMetrics, currency).map((group) => ({
    ...group,
    items: group.items.filter((item) => item.value != null),
  }));
  const hasMoreMetrics = metricGroups.some((group) => group.items.length > 0);

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">Stats</h3>
        {hasMoreMetrics && (
          <button type="button" className="ec-inline-link-btn" onClick={() => setIsSeeAllOpen(true)}>
            See all
          </button>
        )}
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
          {
            label: "Market cap",
            value:
              marketProfile?.market_cap != null
                ? formatCompactCurrency(marketProfile.market_cap, currency)
                : null,
          },
          { label: "P/E ratio", value: formatRatio(marketMetrics?.pe_ratio) },
          { label: "Beta", value: marketProfile?.beta != null ? marketProfile.beta.toFixed(2) : null },
          { label: "Volatility", value: formatPercent(marketMetrics?.volatility) },
          {
            label: "Dividend yield",
            value: marketProfile?.dividend_yield != null ? `${(marketProfile.dividend_yield * 100).toFixed(2)}%` : null,
          },
          {
            label: "Dividend rate",
            value:
              marketProfile?.dividend_rate != null
                ? formatCurrency(marketProfile.dividend_rate, currency)
                : null,
          },
          { label: "Dividend frequency", value: formatDividendFrequency(marketProfile?.dividend_frequency) },
          {
            label: "Payout ratio",
            value: marketProfile?.payout_ratio != null ? `${(marketProfile.payout_ratio * 100).toFixed(2)}%` : null,
          },
        ]}
      />

      <Drawer open={isSeeAllOpen} onClose={() => setIsSeeAllOpen(false)} title="All metrics">
        {metricGroups
          .filter((group) => group.items.length > 0)
          .map((group) => (
            <div className="ec-metrics-group" key={group.title}>
              <h4 className="ec-metrics-group-title">{group.title}</h4>
              <FieldList items={group.items} />
            </div>
          ))}
      </Drawer>
    </Card>
  );
}

export default HoldingStatsPanel;
