import { useState } from "react";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import HoldingDividendBarChart from "./HoldingDividendBarChart.jsx";
import {
  DIVIDEND_HISTORY_RANGES,
  UPCOMING_DIVIDEND_RANGES,
  formatPrice,
  selectDividendHistory,
  selectUpcomingDividends,
  selectUpcomingDividendsInRange,
} from "./holdingFinancials.js";
import "../accounts/PriceChart.css";

/** A plain "YYYY-MM-DD" date string as "10 Sep 2026" — same short format
 * HoldingAboutSection's formatIpoDate uses for a profile date, just without
 * that one's ISO-*datetime* parsing (ex_dividend_date/payment_date have no
 * time component to strip). */
function formatDividendDate(isoDate) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** One dividend card's contents — the per-share amount, a Declared/
 * Estimated badge, and the ex-dividend date, with the payment date
 * alongside it (side by side) when a Declared card has one. Used by the
 * main section's capped grid only — the "See all" drawer's Upcoming view
 * is a bar chart instead (see HoldingDividendBarChart.jsx). */
function DividendCard({ card }) {
  return (
    <div className="ec-dividend-card">
      <Badge tone={card.status === "declared" ? "success" : "info"}>
        {card.status === "declared" ? "Declared" : "Estimated"}
      </Badge>
      <Balance as="span" className="ec-dividend-amount">
        {formatPrice(card.price, card.currency)}
      </Balance>
      <div className="ec-dividend-fields-row">
        <div className="ec-dividend-field">
          <span className="ec-dividend-field-label">Ex-dividend date</span>
          <span className="ec-dividend-field-value">{formatDividendDate(card.ex_dividend_date)}</span>
        </div>
        {card.status === "declared" && card.payment_date && (
          <div className="ec-dividend-field">
            <span className="ec-dividend-field-label">Payment date</span>
            <span className="ec-dividend-field-value">{formatDividendDate(card.payment_date)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Up to MAX_UPCOMING_DIVIDENDS upcoming-dividend cards (see
 * holdingFinancials.js's `selectUpcomingDividends`), plus a "See all"
 * button opening a Drawer with a single Past/Upcoming toggle button (one
 * button showing the currently active view's label; clicking it flips to
 * the other view, same swap-in-place pattern as the app's dark/light
 * ThemeToggle) - each view is its own bar chart with its own range picker:
 *  - "Past": every real historical payout, ranged 1Y/2Y/3Y/5Y/10Y/MAX
 *    (same long-horizon picker as the price chart), defaulting to 1Y.
 *  - "Upcoming": every declared/estimated record due within the selected
 *    range - same dedup rule as the card grid (a declared record wins over
 *    an overlapping estimate) but windowed by date instead of capped by
 *    count - ranged 1Y/2Y/3Y/5Y/10Y (no MAX: a forecast never projects
 *    past 10 years out), defaulting to 1Y. Bars are colored green/blue to
 *    match the Declared/Estimated badge tones.
 *
 * Renders nothing when `dividends` is null (no data published yet) or
 * carries no records at all (paid, declared, or estimated).
 *
 * @param {{ dividends: import("../../api/market.js").DividendsResponse|null }} props
 */
function HoldingDividendsSection({ dividends }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerView, setDrawerView] = useState("past");
  const [historyRangeId, setHistoryRangeId] = useState("1y");
  const [upcomingRangeId, setUpcomingRangeId] = useState("1y");

  const allDividends = dividends?.dividends ?? [];
  if (allDividends.length === 0) return null;

  const currency = allDividends[0]?.currency ?? null;
  const upcomingCards = selectUpcomingDividends(allDividends);
  const pastRecords = selectDividendHistory(allDividends, historyRangeId);
  const upcomingRecords = selectUpcomingDividendsInRange(allDividends, upcomingRangeId);

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">Dividends</h3>
        <button type="button" className="ec-inline-link-btn" onClick={() => setIsDrawerOpen(true)}>
          See all
        </button>
      </div>

      {upcomingCards.length > 0 ? (
        <div className="ec-dividend-grid">
          {upcomingCards.map((card) => (
            <DividendCard card={card} key={`${card.status}-${card.ex_dividend_date}`} />
          ))}
        </div>
      ) : (
        <p className="ec-chart-caption">No upcoming dividends declared or estimated yet.</p>
      )}

      <Drawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="Dividends">
        <button
          type="button"
          className="ec-dividend-view-toggle"
          onClick={() => setDrawerView((current) => (current === "past" ? "upcoming" : "past"))}
          aria-label={`Switch to ${drawerView === "past" ? "Upcoming" : "Past"} view`}
        >
          <i className="bi bi-arrow-left-right" aria-hidden="true" />
          {drawerView === "past" ? "Past" : "Upcoming"}
        </button>

        {drawerView === "past" ? (
          <div>
            <div className="ec-pchart-ranges" role="group" aria-label="Dividend history range">
              {DIVIDEND_HISTORY_RANGES.map((range) => (
                <button
                  key={range.id}
                  type="button"
                  className={`ec-pchart-range-btn${range.id === historyRangeId ? " is-active" : ""}`}
                  onClick={() => setHistoryRangeId(range.id)}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <HoldingDividendBarChart
              records={pastRecords}
              currency={currency}
              emptyMessage="No dividend history in this range."
            />
          </div>
        ) : (
          <div>
            <div className="ec-pchart-ranges" role="group" aria-label="Upcoming dividends range">
              {UPCOMING_DIVIDEND_RANGES.map((range) => (
                <button
                  key={range.id}
                  type="button"
                  className={`ec-pchart-range-btn${range.id === upcomingRangeId ? " is-active" : ""}`}
                  onClick={() => setUpcomingRangeId(range.id)}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <HoldingDividendBarChart
              records={upcomingRecords}
              currency={currency}
              colorByStatus
              emptyMessage="No upcoming dividends declared or estimated in this range."
            />
          </div>
        )}
      </Drawer>
    </Card>
  );
}

export default HoldingDividendsSection;
