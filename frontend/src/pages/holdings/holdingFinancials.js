import { getPrices, getProfile } from "../../api/market.js";
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
 * An FX rate as a "1:1" ratio using each side's real currency symbol (e.g.
 * "£1 : $1.2734"), matching how brokerage apps like Trading 212/Chip quote
 * a rate — rather than a bare unlabeled number, which reads ambiguously
 * once you're not sure which currency it's even rate-per-1-unit-of.
 * `baseCurrency` is the "1" side (see HoldingTransactionsSection.jsx's
 * `displayFxRate` — the default→native direction the transaction form
 * itself shows/accepts), `quoteCurrency` the side `rate` is quoted in.
 * `null` when `rate` is unset.
 *
 * @param {number|null|undefined} rate
 * @param {string} baseCurrency
 * @param {string} quoteCurrency
 * @returns {string|null}
 */
export function formatFxRatio(rate, baseCurrency, quoteCurrency) {
  if (rate == null) return null;
  const base = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: baseCurrency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(1);
  const quote = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: quoteCurrency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(rate);
  return `${base} : ${quote}`;
}

/**
 * @typedef {Object} InstanceFinancials
 * @property {number} shares - net shares currently held.
 * @property {number|null} avgPriceNative - null when there are no
 *   transactions recorded yet for this holding.
 * @property {number} invested - shares * avgPriceNative (0 when avgPriceNative is null).
 * @property {number} dividendsNative - total dividend cash received so far,
 *   in the holding's own native currency (holding.dividends_native — see
 *   equicast_core.transactions.compute_holding_rollup).
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

/** Cards `selectRecentTransactions` returns, most recent first. */
export const MAX_RECENT_TRANSACTIONS = 5;

/**
 * The `limit` most recent BUY/SELL/DIVIDEND records across `transactions`
 * (already merged across every instance of a ticker by the caller — a
 * TRANSACTION-mode holding logs discrete events, so unlike the AVERAGE-mode
 * position card there's no single "current" record to show, just the
 * latest activity), most recent first — mirrors AVERAGE mode's own card
 * grid folding BUY and DIVIDEND into one merged, date-sorted list.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @param {number} [limit]
 * @returns {import("../../api/transactions.js").Transaction[]}
 */
export function selectRecentTransactions(transactions, limit = MAX_RECENT_TRANSACTIONS) {
  return transactions
    .filter((t) => t.type === "BUY" || t.type === "SELL" || t.type === "DIVIDEND")
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))
    .slice(0, limit);
}

/**
 * Net shares currently held for one TRANSACTION-mode holding — sum of its
 * BUY records minus its SELL records, in whatever order they happen to be
 * stored (not date-ordered), mirroring the net-shares check
 * `equicast_core.transactions.TransactionsClient.create_transaction` itself
 * runs server-side for a SELL. Used client-side only to decide which
 * instances are even eligible for "Add Sell" (a holding with 0 net shares
 * has nothing left to sell) — the backend is still the source of truth for
 * whether a given SELL quantity is actually allowed.
 *
 * @param {import("../../api/transactions.js").Transaction[]} transactions
 * @returns {number}
 */
export function selectNetShares(transactions) {
  return transactions.reduce((net, t) => {
    if (t.type === "BUY") return net + Number(t.no_of_shares);
    if (t.type === "SELL") return net - Number(t.no_of_shares);
    return net;
  }, 0);
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
 * @returns {{ shares: number, invested: number, dividendsNative: number, currentValue: number|null, plValue: number|null, plPct: number|null }}
 */
export function rollupInstances(instanceFinancials, currentPriceNative) {
  const shares = instanceFinancials.reduce((sum, f) => sum + f.shares, 0);
  const invested = instanceFinancials.reduce((sum, f) => sum + f.invested, 0);
  const dividendsNative = instanceFinancials.reduce((sum, f) => sum + (f.dividendsNative ?? 0), 0);

  if (currentPriceNative == null) {
    return { shares, invested, dividendsNative, currentValue: null, plValue: null, plPct: null };
  }
  const currentValue = shares * currentPriceNative;
  const plValue = currentValue - invested;
  const plPct = invested !== 0 ? (plValue / invested) * 100 : 0;
  return { shares, invested, dividendsNative, currentValue, plValue, plPct };
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

/** The latest bar with `bar.date <= date` across `history`'s three
 * segments (`daily`/`weekly`/`monthly` — see api/market.js's PriceSeries),
 * checked in that order since it's the most precise available: an older
 * `date` simply won't have any `daily`/`weekly` bar at or before it (both
 * only cover a recent window), falling through to `monthly`'s full
 * history. Mirrors the backend's own "nearest trading day on or before"
 * semantics (equicast_core.client.get_price_on_date/get_fx_rate_on_date),
 * just computed client-side against an already-fetched series instead of
 * a network call per date. `null` if no segment has anything that old. */
function findCloseOnOrBefore(history, date) {
  for (const bars of [history?.daily, history?.weekly, history?.monthly]) {
    if (!bars || bars.length === 0) continue;
    let candidate = null;
    for (const bar of bars) {
      if (bar.date > date) break;
      candidate = bar;
    }
    if (candidate) return candidate.close;
  }
  return null;
}

/**
 * Resolves the historical FX rate from `fromCurrency` to `toCurrency` as of
 * `date` (the nearest published trading day on or before it) — the "1
 * fromCurrency = X toCurrency" rate a transaction dated `date` would
 * convert at. Unlike `resolveFxRate` above (a *current* rate, off the
 * profile endpoint's `day_close`), this is entirely resolved from each
 * pair's own bundled price history (`getPrices`, already IndexedDB-cached
 * same-day — see priceCache.js) via `findCloseOnOrBefore`: one fetch per
 * pair per day covers every date a user might pick, rather than a network
 * round trip per date. Tries the direct pair first, then the inverted pair
 * (taking its reciprocal) if that's what's published instead, same
 * fallback `resolveFxRate` uses. Never throws — any failure (no pair
 * published, a network error, nothing that far back in either pair's
 * history) resolves to `null` so a caller can show "—" instead of
 * blocking on this lookup.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string|null|undefined} fromCurrency
 * @param {string|null|undefined} toCurrency
 * @param {string|null|undefined} date - "YYYY-MM-DD"
 * @returns {Promise<number|null>}
 */
export async function resolveFxRateOnDate(api, fromCurrency, toCurrency, date) {
  if (!fromCurrency || !toCurrency || !date) return null;
  if (fromCurrency === toCurrency) return 1;

  try {
    const direct = await getPrices(api, "fx", `${fromCurrency}${toCurrency}`);
    const rate = findCloseOnOrBefore(direct, date);
    if (typeof rate === "number" && rate > 0) return rate;
  } catch {
    // No direct pair published — fall through and try the inverted one.
  }

  try {
    const inverted = await getPrices(api, "fx", `${toCurrency}${fromCurrency}`);
    const rate = findCloseOnOrBefore(inverted, date);
    if (typeof rate === "number" && rate > 0) return 1 / rate;
  } catch {
    // Neither pair is published for this currency combination, or neither
    // has anything published as far back as `date`.
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
 * Every range the "See all" drawer's dividend chart offers on its past
 * (history) side - the same long-horizon tail of market.js's PRICE_RANGES
 * the price chart uses (1y/2y/3y/5y/10y), minus the short ranges
 * (5d/1m/6m/ytd) that don't apply here: dividend payouts are sparse
 * discrete events, not a daily series, so a short window would show at
 * most one or two points. No "MAX": `availablePastRanges` below already
 * folds "show everything" into whichever preset first reaches the real
 * earliest date, so a separate id for the same thing would be redundant.
 */
export const DIVIDEND_HISTORY_RANGES = [
  { id: "1y", label: "1Y" },
  { id: "2y", label: "2Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "10y", label: "10Y" },
];

/** `cutoff` years before/after `today` (sign of `direction`), as a plain
 * "YYYY-MM-DD" — shared by `availablePastRanges`/`availableForecastRanges`
 * (deciding which range buttons are worth showing at all) and
 * `selectDividendHistory`/`selectUpcomingDividendsInRange` (the actual
 * filter cutoff for a chosen range). */
function yearsFromToday(years, direction) {
  const date = new Date();
  date.setFullYear(date.getFullYear() + direction * years);
  return date.toISOString().slice(0, 10);
}

/**
 * Which of `DIVIDEND_HISTORY_RANGES` are worth offering at all, given
 * `earliestDate` (the real earliest ex-dividend date this chart could ever
 * show — the ticker's own first paid dividend when the holding isn't
 * owned, or this position's own first received dividend when it is —
 * `null` while that's still unresolved skips filtering entirely, showing
 * every preset). A preset whose own cutoff already reaches back on/before
 * `earliestDate` would show the exact same data as any larger preset — so
 * only the *first* (smallest) preset that reaches that far is kept, as the
 * de facto "show everything" option, and every larger one past it is
 * dropped as redundant (GitHub request: "if the holding itself doesn't
 * have 10Y history, 10Y doesn't make sense"). Always returns at least one
 * range. */
export function availablePastRanges(earliestDate) {
  if (!earliestDate) return DIVIDEND_HISTORY_RANGES;
  const kept = [];
  for (const range of DIVIDEND_HISTORY_RANGES) {
    kept.push(range);
    const cutoff = yearsFromToday(Number.parseInt(range.id, 10), -1);
    if (cutoff <= earliestDate) break;
  }
  return kept;
}

/**
 * `dividends`' `"paid"` (already-happened) records only, ascending by
 * ex-dividend date, trimmed to `rangeId` (one of `DIVIDEND_HISTORY_RANGES`'
 * ids). `sinceDate` (this position's own first received dividend, when
 * owned) raises the floor further when it's later than `rangeId`'s own
 * cutoff — e.g. a "10Y" pick still never shows anything before a position
 * that's only 2 years old. Unlike `getPrices`' server-side range trimming,
 * this filters client-side: the whole dividend history is already in one
 * small `GET .../dividends/` response (see market.js's DividendsResponse),
 * not worth a second round trip just to change the chart's window.
 *
 * @param {import("../../api/market.js").DividendRecord[]} dividends
 * @param {string} rangeId
 * @param {string|null} [sinceDate]
 * @returns {import("../../api/market.js").DividendRecord[]}
 */
export function selectDividendHistory(dividends, rangeId, sinceDate = null) {
  const paid = dividends
    .filter((record) => record.status === "paid")
    .sort((a, b) => a.ex_dividend_date.localeCompare(b.ex_dividend_date));

  const rangeCutoff = yearsFromToday(Number.parseInt(rangeId, 10), -1);
  const floor = sinceDate && sinceDate > rangeCutoff ? sinceDate : rangeCutoff;
  return paid.filter((record) => record.ex_dividend_date >= floor);
}

/**
 * Every range the "See all" drawer's forecast overlay offers - same
 * 1Y/2Y/3Y/5Y/10Y tail as `DIVIDEND_HISTORY_RANGES`, just projecting
 * forward from today instead of back from it.
 */
export const UPCOMING_DIVIDEND_RANGES = [
  { id: "1y", label: "1Y" },
  { id: "2y", label: "2Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "10y", label: "10Y" },
];

/**
 * Which of `UPCOMING_DIVIDEND_RANGES` are worth offering, mirroring
 * `availablePastRanges` in the opposite direction: `latestForecastDate`
 * (the furthest-out declared/estimated ex-dividend date this ticker's
 * market data actually reaches — `null` skips filtering) caps how far a
 * forecast could ever usefully extend, since `equicast_forecasting.
 * dividends` itself never projects past its own ~10-year horizon anyway.
 * Always returns at least one range. */
export function availableForecastRanges(latestForecastDate) {
  if (!latestForecastDate) return UPCOMING_DIVIDEND_RANGES;
  const kept = [];
  for (const range of UPCOMING_DIVIDEND_RANGES) {
    kept.push(range);
    const cutoff = yearsFromToday(Number.parseInt(range.id, 10), 1);
    if (cutoff >= latestForecastDate) break;
  }
  return kept;
}

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
