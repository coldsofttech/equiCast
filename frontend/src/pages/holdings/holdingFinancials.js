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
