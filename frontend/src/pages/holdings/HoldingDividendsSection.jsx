import { useEffect, useState } from "react";
import { useApi } from "../../api/useApi.js";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import HoldingDividendBarChart from "./HoldingDividendBarChart.jsx";
import {
  DIVIDEND_HISTORY_RANGES,
  UPCOMING_DIVIDEND_RANGES,
  formatPrice,
  resolveFxRate,
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

/** One dividend card's contents — a Declared/Estimated badge, the
 * ex-dividend date, with the payment date alongside it (side by side) when
 * a Declared card has one. `currency` comes from the wrapping
 * `DividendsResponse` (see `DividendsResponse.currency` — an individual
 * `DividendRecord` carries no currency of its own), one payout currency for
 * the whole ticker — `formatPrice` already renders its symbol as part of
 * the amount, so nothing else here repeats it. The headline amount is the
 * per-share payout (`card.price`) when the ticker isn't owned — nothing to
 * multiply it by — or, once `sharesOwned` is positive, that payout's total
 * value for the position (`card.price * sharesOwned`), with the per-share
 * rate kept underneath for reference. When `fxRate` has resolved and
 * differs from a straight 1:1 (`currency` differs from `defaultCurrency`),
 * both figures switch to the converted (default-currency) amount as the
 * headline — same "converted first" convention Value/Invested use — with
 * the native amount kept alongside in parens, same as the Owned Shares
 * table's native/converted column pair. Falls back to native-only
 * (today's behavior) while the rate is still loading or unresolved. Used
 * by the main section's capped grid only — the "See all" drawer's Upcoming
 * view is a bar chart instead (see HoldingDividendBarChart.jsx), still
 * per-share and native-currency-only regardless of ownership. */
function DividendCard({ card, currency, sharesOwned, defaultCurrency, fxRate }) {
  const isOwned = sharesOwned > 0;
  const amount = isOwned ? card.price * sharesOwned : card.price;
  const showConverted = fxRate != null && defaultCurrency && currency !== defaultCurrency;
  const headlineAmount = showConverted ? amount * fxRate : amount;
  const headlineCurrency = showConverted ? defaultCurrency : currency;
  const perShareAmount = showConverted ? card.price * fxRate : card.price;
  const perShareCurrency = showConverted ? defaultCurrency : currency;

  return (
    <div className="ec-dividend-card">
      <Badge tone={card.status === "declared" ? "success" : "info"}>
        {card.status === "declared" ? "Declared" : "Estimated"}
      </Badge>
      <span className="ec-dividend-amount-row">
        <Balance as="span" className="ec-dividend-amount">
          {formatPrice(headlineAmount, headlineCurrency)}
        </Balance>
        {showConverted && (
          <span className="ec-dividend-native-amount">({formatPrice(amount, currency)})</span>
        )}
      </span>
      {isOwned && (
        <span className="ec-dividend-field-label">
          {formatPrice(perShareAmount, perShareCurrency)}/share
          {showConverted && ` (${formatPrice(card.price, currency)})`}
        </span>
      )}
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
 * @param {{
 *   dividends: import("../../api/market.js").DividendsResponse|null,
 *   sharesOwned?: number,
 *   defaultCurrency?: string|null,
 * }} props `sharesOwned` — total shares held across every instance of this
 *   ticker (0 or omitted when not owned) — scales each card's headline
 *   amount from a per-share payout to that payout's total value for the
 *   position; see `DividendCard`. `defaultCurrency` — the user's own
 *   default currency (see `UserProfile`); once resolved to an FX rate
 *   against `dividends.currency`, each card's headline switches from the
 *   ticker's native currency to this one, same as the Value/Invested stat
 *   tiles above.
 */
function HoldingDividendsSection({ dividends, sharesOwned = 0, defaultCurrency = null }) {
  const api = useApi();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerView, setDrawerView] = useState("past");
  const [historyRangeId, setHistoryRangeId] = useState("1y");
  const [upcomingRangeId, setUpcomingRangeId] = useState("1y");
  const [fxRate, setFxRate] = useState(null);

  const allDividends = dividends?.dividends ?? [];
  const currency = dividends?.currency ?? null;

  // Today's latest rate, not a historical one — these cards cover
  // declared/estimated payouts that haven't happened yet, so there's no
  // past date to look a rate up for (same reasoning computeHoldingValuation
  // uses today's rate for a holding's live Value).
  useEffect(() => {
    if (!currency || !defaultCurrency || currency === defaultCurrency) {
      setFxRate(null);
      return undefined;
    }
    let cancelled = false;
    resolveFxRate(api, currency, defaultCurrency).then((rate) => {
      if (!cancelled) setFxRate(rate);
    });
    return () => {
      cancelled = true;
    };
  }, [api, currency, defaultCurrency]);

  if (allDividends.length === 0) return null;

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
            <DividendCard
              card={card}
              currency={currency}
              sharesOwned={sharesOwned}
              defaultCurrency={defaultCurrency}
              fxRate={fxRate}
              key={`${card.status}-${card.ex_dividend_date}`}
            />
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
