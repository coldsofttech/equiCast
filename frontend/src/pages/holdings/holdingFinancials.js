import { seededRandom } from "../../utils/deterministicRandom.js";
import { getProfile } from "../../api/market.js";
import { formatCurrency } from "../sampleFinancials.js";

/**
 * Real (not synthetic) financial calculations for the holding detail page —
 * mirrors sampleFinancials.js's separation of pure calculation logic from
 * JSX, but everything here is derived from actual transactions/prices
 * rather than a seeded random walk. The only synthetic values left on this
 * page are the four metrics `buildPlaceholderMetrics` produces, for the
 * fields no backend endpoint exposes yet (P/E ratio, volatility, average
 * volume, dividend frequency) — every other figure here is real.
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
 * @typedef {Object} InstanceFinancials
 * @property {number} shares - net shares currently held.
 * @property {number|null} avgPriceNative - null when there are no
 *   transactions recorded yet for this holding.
 * @property {number} invested - shares * avgPriceNative (0 when avgPriceNative is null).
 */

/**
 * An AVERAGE-mode account has at most one transaction record per holding —
 * a mutable running snapshot rather than a log (see
 * equicast_core.transactions's module docstring) — so this is a direct
 * read, not a rollup.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @returns {InstanceFinancials}
 */
export function deriveAverageModeFinancials(transactions) {
  const record = transactions[0];
  if (!record) return { shares: 0, avgPriceNative: null, invested: 0 };
  const shares = Number(record.no_of_shares);
  const avgPriceNative = Number(record.average_price);
  return { shares, avgPriceNative, invested: shares * avgPriceNative };
}

/**
 * A TRANSACTION-mode account logs discrete BUY/SELL events with no
 * computed average price stored anywhere (see equicast_core.transactions's
 * module docstring) — this derives one via the weighted-average-cost
 * method: each BUY adds to the running cost basis at its own price; each
 * SELL removes shares at the *current* running average cost (not FIFO lot
 * tracking), leaving the average cost of whatever remains unchanged. This
 * is the same method most brokerage "average cost" statements use, and the
 * simplest one that stays correct through repeated buys/sells without
 * tracking individual lots.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @returns {InstanceFinancials}
 */
export function deriveTransactionModeFinancials(transactions) {
  const sorted = [...transactions].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""));

  let shares = 0;
  let cost = 0;
  for (const record of sorted) {
    const qty = Number(record.no_of_shares);
    const price = Number(record.price);
    if (record.type === "BUY") {
      shares += qty;
      cost += qty * price;
    } else if (record.type === "SELL" && shares > 0) {
      const costPerShare = cost / shares;
      const sold = Math.min(qty, shares);
      cost -= sold * costPerShare;
      shares -= sold;
    }
  }

  return {
    shares,
    avgPriceNative: shares > 0 ? cost / shares : null,
    invested: shares > 0 ? cost : 0,
  };
}

/**
 * Dispatches to the AVERAGE/TRANSACTION derivation above based on the
 * holding's owning account's transaction_type.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @param {"AVERAGE"|"TRANSACTION"} transactionType
 * @returns {InstanceFinancials}
 */
export function deriveInstanceFinancials(transactions, transactionType) {
  return transactionType === "TRANSACTION"
    ? deriveTransactionModeFinancials(transactions)
    : deriveAverageModeFinancials(transactions);
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
    const rate = direct.day_close ?? direct.day_average;
    if (typeof rate === "number" && rate > 0) return rate;
  } catch {
    // No direct pair published — fall through and try the inverted one.
  }

  try {
    const inverted = await getProfile(api, "fx", `${defaultCurrency}${nativeCurrency}`);
    const rate = inverted.day_close ?? inverted.day_average;
    if (typeof rate === "number" && rate > 0) return 1 / rate;
  } catch {
    // Neither pair is published for this currency combination.
  }

  return null;
}

/**
 * @typedef {Object} PriceWindow
 * @property {number|null} high
 * @property {number|null} low
 * @property {number[]} closes
 * @property {boolean} sufficient - false when there's too little published
 *   price history for a meaningful high/low or sparkline (e.g. a ticker
 *   published only a handful of trading days ago).
 */

/**
 * The last `tradingDays` entries of `priceResults` (ascending/oldest-first
 * — see market.js's getPrices), for the Stats panel's 1 Week / 1 Year
 * high-low. `sufficient` requires at least 3 days (or fewer if
 * `tradingDays` itself is smaller) so a 1-2-point "chart" is never rendered.
 *
 * @param {import("../../api/market.js").PriceBar[]|null|undefined} priceResults
 * @param {number} tradingDays
 * @returns {PriceWindow}
 */
export function extractPriceWindow(priceResults, tradingDays) {
  if (!priceResults || priceResults.length === 0) {
    return { high: null, low: null, closes: [], sufficient: false };
  }
  const slice = priceResults.slice(-tradingDays);
  const highs = slice.map((r) => r.high);
  const lows = slice.map((r) => r.low);
  const closes = slice.map((r) => r.close);
  return {
    high: Math.max(...highs),
    low: Math.min(...lows),
    closes,
    sufficient: slice.length >= Math.min(3, tradingDays),
  };
}

/**
 * Dividend payout schedules this seeds between, for `buildPlaceholderMetrics`.
 */
const DIVIDEND_FREQUENCIES = ["Quarterly", "Semi-annual", "Annual", "Monthly"];

/**
 * Seeded-random placeholder values for the four metrics no backend endpoint
 * exposes yet (see backend/market_data/views.py — no MetricsView, and
 * packages/metrics's computed fundamentals are never read back out at
 * request time). Deterministic per ticker via the same seeded-random
 * approach every other illustrative value in this app uses (see
 * deterministicRandom.js) so a given ticker's placeholder numbers don't
 * reshuffle on every render. Every field returned here MUST be rendered
 * with an explicit "Sample data" hint (see StatTile's `hint` prop) — this
 * is the only synthetic data on the whole page.
 *
 * @param {string} ticker
 * @returns {{ peRatio: number, volatilityPct: number, avgVolume: number, dividendFrequency: string }}
 */
export function buildPlaceholderMetrics(ticker) {
  const rand = seededRandom(`holding-metrics:${ticker}`);
  return {
    peRatio: 8 + rand() * 40,
    volatilityPct: 10 + rand() * 50,
    avgVolume: Math.round(100000 + rand() * 20000000),
    dividendFrequency: DIVIDEND_FREQUENCIES[Math.floor(rand() * DIVIDEND_FREQUENCIES.length)],
  };
}
