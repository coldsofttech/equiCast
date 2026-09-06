import { getProfile } from "../../api/market.js";
import { formatCurrency } from "../sampleFinancials.js";

/**
 * Real (not synthetic) financial calculations for the holding detail page —
 * mirrors sampleFinancials.js's separation of pure calculation logic from
 * JSX, but everything here is derived from actual transactions/prices
 * rather than a seeded random walk. Every figure on the page is real,
 * including dividend frequency (the profile's own `dividend_frequency`
 * field — see `formatDividendFrequency` below), P/E ratio/volatility/every
 * other Stats metric, all sourced from `GET .../metrics/` (see `market.js`'s
 * `getMetrics`).
 */

export { formatCurrency };

/**
 * Per-share price formatting — formatCurrency's maximumFractionDigits:0 is
 * too lossy for a share price like $34.56. Falls back to a plain 2-decimal
 * number (no currency symbol) when `currency` is unknown (e.g. the
 * instrument's profile 404'd, so its native currency was never resolved).
 *
 * @param {number} value
 * @param {string|null|undefined} currency
 * @returns {string}
 */
export function formatPrice(value, currency) {
  if (!currency) return value.toFixed(2);
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * A large figure like market cap rendered in K/M/B/T notation (e.g.
 * $4.67T) rather than formatCurrency's full digit string — unreadable at a
 * glance once it's 13 digits long. Locale is pinned to "en-US" rather than
 * following the viewer's own locale — compact notation's abbreviations
 * aren't just digit grouping, they vary by locale (e.g. British English
 * renders 1e9/1e12 as "1bn"/"1tn" instead of "1B"/"1T"), and K/M/B/T is
 * what this is meant to show regardless of viewer.
 *
 * @param {number} value
 * @param {string|null|undefined} currency
 * @returns {string}
 */
export function formatCompactCurrency(value, currency) {
  if (!currency) {
    return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(
      value
    );
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * A metrics fraction (e.g. 0.23, -0.08) as a percentage string, `null` when
 * unset — same "skip, don't dash" contract FieldList expects. Most of
 * equicast-metrics' fundamentals/risk fields are fractions (see
 * `equicast_metrics.fundamentals`/`.calculations`); `debt_to_equity` is the
 * one exception, already scaled to a percentage by the backend, so callers
 * format that one as a plain number with a literal "%" instead.
 *
 * @param {number|null|undefined} fraction
 * @param {number} [digits]
 * @returns {string|null}
 */
export function formatPercent(fraction, digits = 1) {
  return fraction != null ? `${(fraction * 100).toFixed(digits)}%` : null;
}

/**
 * A plain decimal ratio (P/E, PEG, price-to-book, Sharpe ratio, ...),
 * `null` when unset.
 *
 * @param {number|null|undefined} value
 * @param {number} [digits]
 * @returns {string|null}
 */
export function formatRatio(value, digits = 2) {
  return value != null ? value.toFixed(digits) : null;
}

/**
 * @typedef {Object} InstanceFinancials
 * @property {number} shares - net shares currently held.
 * @property {number|null} avgPriceNative - null when there are no
 *   transactions recorded yet for this holding.
 * @property {number} invested - shares * avgPriceNative (0 when avgPriceNative is null).
 */

/**
 * An AVERAGE-mode holding has at most one BUY-type record — a mutable
 * running snapshot the user corrects over time rather than a log entry
 * (see equicast_core.transactions's module docstring) — plus, alongside
 * it, any number of DIVIDEND-type records that don't affect shares/cost.
 * A legacy record predating the BUY/DIVIDEND shape still has `type: null`;
 * treated the same as `"BUY"` here, same as the backend does.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @returns {import("../../api/transactions.js").Transaction|null}
 */
export function selectPositionEntry(transactions) {
  return transactions.find((t) => t.type === "BUY" || t.type == null) ?? null;
}

/** Cards `selectRecentTradeTransactions` returns, most recent first. */
export const MAX_RECENT_TRANSACTIONS = 5;

/**
 * The `limit` most recent BUY/SELL records across `transactions` (already
 * merged across every instance of a ticker by the caller — a TRANSACTION-
 * mode holding logs discrete events, so unlike the AVERAGE-mode position
 * card there's no single "current" record to show, just the latest
 * activity), most recent first. DIVIDEND records are excluded here — this
 * is deliberately just the buy/sell activity feed the Transactions panel's
 * card grid shows; see `selectDividendEntries` for dividends.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @param {number} [limit]
 * @returns {import("../../api/transactions.js").Transaction[]}
 */
export function selectRecentTradeTransactions(transactions, limit = MAX_RECENT_TRANSACTIONS) {
  return transactions
    .filter((t) => t.type === "BUY" || t.type === "SELL")
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))
    .slice(0, limit);
}

/**
 * Rolls up every instance of one ticker (direct-in-account and/or
 * in-pie, possibly spanning both AVERAGE- and TRANSACTION-mode accounts)
 * into one page-level total. Safe as a plain sum in native currency — every
 * instance's avgPriceNative and the ticker's current price are already in
 * the same currency (the instrument's own), regardless of which account
 * currency each instance's parent account uses. `currentValue`/`plValue`/
 * `plPct` are `null` (not 0) when `currentPriceNative` is unknown, so the
 * page can render "—" instead of a misleading $0/0%.
 *
 * @param {InstanceFinancials[]} instanceFinancials
 * @param {number|null} currentPriceNative
 * @returns {{ shares: number, invested: number, currentValue: number|null, plValue: number|null, plPct: number|null }}
 */
export function rollupInstances(instanceFinancials, currentPriceNative) {
  const shares = instanceFinancials.reduce((sum, f) => sum + f.shares, 0);
  const invested = instanceFinancials.reduce((sum, f) => sum + f.invested, 0);

  if (currentPriceNative == null) {
    return { shares, invested, currentValue: null, plValue: null, plPct: null };
  }
  const currentValue = shares * currentPriceNative;
  const plValue = currentValue - invested;
  const plPct = invested !== 0 ? (plValue / invested) * 100 : 0;
  return { shares, invested, currentValue, plValue, plPct };
}

/**
 * Resolves a conversion rate from `nativeCurrency` to `defaultCurrency` via
 * the real fx catalog (a plain `<BASE><QUOTE>` ticker, e.g. "USDGBP" quotes
 * GBP per 1 USD — see packages/fx's published output) using the same
 * profile endpoint stock/etf holdings use. Tries the direct pair first,
 * then the inverted pair (taking its reciprocal) if that's what's
 * published instead. Never throws — any failure (no pair published, a
 * network error) resolves to `null` so a caller can show "—" rather than
 * block the page on an FX lookup, per this page's explicit design: FX
 * conversion is a nice-to-have on one table column, not a gate.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string|null|undefined} nativeCurrency
 * @param {string|null|undefined} defaultCurrency
 * @returns {Promise<number|null>}
 */
export async function resolveFxRate(api, nativeCurrency, defaultCurrency) {
  if (!nativeCurrency || !defaultCurrency) return null;
  if (nativeCurrency === defaultCurrency) return 1;

  try {
    const direct = await getProfile(api, "fx", `${nativeCurrency}${defaultCurrency}`);
    const rate = direct.day_close;
    if (typeof rate === "number" && rate > 0) return rate;
  } catch {
    // No direct pair published — fall through and try the inverted one.
  }

  try {
    const inverted = await getProfile(api, "fx", `${defaultCurrency}${nativeCurrency}`);
    const rate = inverted.day_close;
    if (typeof rate === "number" && rate > 0) return 1 / rate;
  } catch {
    // Neither pair is published for this currency combination.
  }

  return null;
}

/**
 * Display labels for the profile's `dividend_frequency` field — the raw
 * cadence label `equicast_dividends.dividend_frequency` classifies each
 * ticker into (see packages/dividends/src/equicast_dividends/frequency.py).
 * `not_applicable` (fewer than 2 recorded payouts to measure a cadence
 * from) has no entry here on purpose — it maps to `null` below so the
 * Stats panel skips the row entirely, same as any other unset field.
 */
const DIVIDEND_FREQUENCY_LABELS = {
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  half_yearly: "Semi-annual",
  yearly: "Annual",
  irregular: "Irregular",
};

/**
 * The profile's raw `dividend_frequency` value (e.g. `"quarterly"`) as a
 * display label (e.g. `"Quarterly"`), `null` when unset or
 * `"not_applicable"` (a non-payer, or too little history to classify).
 *
 * @param {string|null|undefined} frequency
 * @returns {string|null}
 */
export function formatDividendFrequency(frequency) {
  return frequency != null ? (DIVIDEND_FREQUENCY_LABELS[frequency] ?? null) : null;
}

/** Max upcoming dividend cards `selectUpcomingDividends` returns — nearest first. */
export const MAX_UPCOMING_DIVIDENDS = 3;

/** Today's date as "YYYY-MM-DD" in the viewer's own local calendar day —
 * same convention as utils/marketDataCache.js's todayKey(), and safe to
 * compare directly against `ex_dividend_date`/`payment_date` since both are
 * already plain ISO date strings, which sort lexicographically the same as
 * chronologically. */
function todayIsoDate() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Picks the `limit` nearest upcoming dividends from `dividends` (as
 * returned by `GET .../dividends/` — see market.js's DividendsResponse),
 * combining `"declared"` (real, yfinance-confirmed) and `"estimated"`
 * (computed projection) records, nearest-dated first. `"paid"` (already-
 * happened) records are always excluded - this is an upcoming-only view.
 * `limit` defaults to `MAX_UPCOMING_DIVIDENDS` (the card section's own
 * cap); pass `Infinity` for the "See all" drawer's uncapped list.
 *
 * `future.parquet` and `forecasting/dividends.parquet` are computed
 * independently (see their own docstrings — `equicast_dividends.
 * DividendsClient.future_dividends`/`equicast_forecasting.dividends`), so
 * an estimated record can land on/before a real declared one for what's
 * really the same payout - whenever a declared record exists, any
 * estimated record on or before its ex-dividend date is dropped so the
 * declared one "wins" for that payout rather than showing both, in both
 * the capped and uncapped list.
 *
 * @param {import("../../api/market.js").DividendRecord[]} dividends
 * @param {number} [limit]
 * @returns {import("../../api/market.js").DividendRecord[]}
 */
export function selectUpcomingDividends(dividends, limit = MAX_UPCOMING_DIVIDENDS) {
  const today = todayIsoDate();
  const upcoming = dividends.filter(
    (record) => record.status !== "paid" && record.ex_dividend_date > today
  );

  const declared = upcoming.filter((record) => record.status === "declared");
  const declaredCutoff = declared.reduce(
    (latest, record) =>
      latest == null || record.ex_dividend_date > latest ? record.ex_dividend_date : latest,
    null
  );
  const estimated = upcoming.filter(
    (record) =>
      record.status === "estimated" &&
      (declaredCutoff == null || record.ex_dividend_date > declaredCutoff)
  );

  return [...declared, ...estimated]
    .sort((a, b) => a.ex_dividend_date.localeCompare(b.ex_dividend_date))
    .slice(0, limit);
}

/**
 * Every range the "See all" drawer's past-dividends chart offers - the
 * same long-horizon tail of market.js's PRICE_RANGES the price chart uses
 * (1y/2y/3y/5y/10y/max), minus the short ranges (5d/1m/6m/ytd) that don't
 * apply here: dividend payouts are sparse discrete events, not a daily
 * series, so a short window would show at most one or two bars.
 */
export const DIVIDEND_HISTORY_RANGES = [
  { id: "1y", label: "1Y" },
  { id: "2y", label: "2Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "10y", label: "10Y" },
  { id: "max", label: "MAX" },
];

/**
 * `dividends`' `"paid"` (already-happened) records only, ascending by
 * ex-dividend date, trimmed to `rangeId` (one of `DIVIDEND_HISTORY_RANGES`'
 * ids) - `"max"` returns every paid record, unfiltered. Unlike
 * `getPrices`' server-side range trimming, this filters client-side: the
 * whole dividend history is already in one small `GET .../dividends/`
 * response (see market.js's DividendsResponse), not worth a second
 * round trip just to change the chart's window.
 *
 * @param {import("../../api/market.js").DividendRecord[]} dividends
 * @param {string} rangeId
 * @returns {import("../../api/market.js").DividendRecord[]}
 */
export function selectDividendHistory(dividends, rangeId) {
  const paid = dividends
    .filter((record) => record.status === "paid")
    .sort((a, b) => a.ex_dividend_date.localeCompare(b.ex_dividend_date));
  if (rangeId === "max") return paid;

  const years = Number.parseInt(rangeId, 10);
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - years);
  const cutoffIsoDate = cutoff.toISOString().slice(0, 10);
  return paid.filter((record) => record.ex_dividend_date >= cutoffIsoDate);
}

/**
 * Every range the "See all" drawer's Upcoming tab offers - same
 * 1Y/2Y/3Y/5Y/10Y tail as `DIVIDEND_HISTORY_RANGES`, minus "MAX": a
 * forecast never projects past `equicast_forecasting.dividends`' own
 * 10-year horizon, so "no cap" would be identical to "10Y" here.
 */
export const UPCOMING_DIVIDEND_RANGES = [
  { id: "1y", label: "1Y" },
  { id: "2y", label: "2Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "10y", label: "10Y" },
];

/**
 * Every upcoming (declared/estimated) record from `dividends` due on or
 * before `rangeId` years from today (one of `UPCOMING_DIVIDEND_RANGES`'
 * ids) - same dedup rule as `selectUpcomingDividends` (a declared record
 * wins over an overlapping estimated one), just windowed by date instead
 * of capped by count.
 *
 * @param {import("../../api/market.js").DividendRecord[]} dividends
 * @param {string} rangeId
 * @returns {import("../../api/market.js").DividendRecord[]}
 */
export function selectUpcomingDividendsInRange(dividends, rangeId) {
  const years = Number.parseInt(rangeId, 10);
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() + years);
  const cutoffIsoDate = cutoff.toISOString().slice(0, 10);

  return selectUpcomingDividends(dividends, Infinity).filter(
    (record) => record.ex_dividend_date <= cutoffIsoDate
  );
}
