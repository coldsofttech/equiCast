import { dividendsCacheKey, readCachedDividends, writeCachedDividends } from "../utils/dividendsCache.js";
import { metricsCacheKey, readCachedMetrics, writeCachedMetrics } from "../utils/metricsCache.js";
import { priceCacheKey, readCachedPrices, writeCachedPrices } from "../utils/priceCache.js";
import { profileCacheKey, readCachedProfile, writeCachedProfile } from "../utils/profileCache.js";

/**
 * @typedef {Object} SearchResult
 * @property {string} ticker
 * @property {string} name
 * @property {"stock"|"etf"|"fx"|"benchmark"|"future"} type
 * @property {number|null} current_price
 * @property {string|null} currency
 * @property {string|null} website
 * @property {number|null} market_cap - a stock's real market cap, an
 *   etf's total assets (fund AUM, the closest comparable "size" figure a
 *   fund has), or `null` for fx/benchmark/future, none of which has a size
 *   concept at all.
 * @property {string|null} exchange - stock/etf/benchmark/future's raw
 *   exchange code (e.g. "NMS"/"PCX"/"SNP"/"CMX"), `null` for fx, which
 *   isn't traded on one.
 * @property {string|null} region - stock/etf/benchmark's short country
 *   code (e.g. "us"/"gb"), `null` for fx (not domiciled anywhere) and
 *   usually `null` for future too (yfinance rarely populates one for a
 *   futures contract).
 * @property {string|null} sector - a stock's own sector (e.g.
 *   "Technology"), `null` for etf/benchmark/future (yfinance never
 *   populates this for any of the three) and fx (no such concept for a
 *   currency pair).
 * @property {string|null} industry - a stock's own industry (e.g.
 *   "Semiconductors"), `null` for etf/benchmark/future/fx for the same
 *   reason as `sector`.
 */

/**
 * @typedef {Object} SearchResponse
 * @property {number} count
 * @property {number} page
 * @property {number} page_size
 * @property {number} total_pages
 * @property {SearchResult[]} results
 */

/**
 * GET /api/market/search/?q=... — see backend/market_data/views.py's
 * SearchView. Ticker/name search across the published catalog (stock/etf/
 * fx/future, plus benchmark when explicitly asked for — see below). Used
 * by TickerSearchField (a portfolio/account holdings picker, triggered
 * explicitly on Enter/a Search click, not on every keystroke — see
 * TickerSearchField.jsx), by SearchPage (the full results page, with
 * `assetClass`/`page` for its Type filter, including "Futures" — see
 * SearchFilters.jsx — and "Load more"), by HoldingComparePicker
 * (`assetClass: "benchmark"`, alongside "stock"/"etf" — see
 * HoldingComparePicker.jsx), and for resolving a currency-pair ticker for
 * FX conversion (`assetClass: "fx"` — see holdings/holdingFinancials.js's
 * resolveFxRate). `assetClass` omitted searches `fx`/`stock`/`etf` only —
 * `benchmark` is opt-in-only, never part of an unfiltered search (see
 * `equicast_core.client.DEFAULT_SEARCH_ASSET_CLASSES`), so TopbarSearch's
 * quick-search and SearchPage's "All types" never surface one; `future`
 * is opt-in the same way for an *unfiltered* search, but — unlike
 * `benchmark` — SearchPage's own Type filter offers it explicitly (see
 * SearchFilters.jsx), so a user can reach it deliberately even though it
 * never appears unasked. `minMarketCap`/`maxMarketCap` (SearchFilters'
 * Market cap range slider), `exchange`, `region`, `sector`, and `industry`
 * (SearchFilters' Exchange/Region/Sector/Industry dropdowns — see
 * pages/search/searchFilterOptions.js for the static option lists) filter
 * stock/etf rows by `market_cap`/`exchange`/`region` and stock rows by
 * `sector`/`industry` respectively; fx rows always match every one of
 * these regardless, while a benchmark/future row is *excluded* whenever
 * `market_cap`/`sector`/`industry` is given (neither has any of those
 * concepts) but still filtered by `exchange`/`region` like stock/etf (see
 * `MarketDataClient.search`'s docstring for why).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} query
 * @param {{ assetClass?: "stock"|"etf"|"fx"|"benchmark"|"future", page?: number, pageSize?: number, minMarketCap?: number, maxMarketCap?: number, exchange?: string, region?: string, sector?: string, industry?: string }} [options]
 * @returns {Promise<SearchResponse>}
 */
export function searchTickers(
  api,
  query,
  {
    assetClass,
    page = 1,
    pageSize = 10,
    minMarketCap,
    maxMarketCap,
    exchange,
    region,
    sector,
    industry,
  } = {}
) {
  const params = new URLSearchParams({ q: query, page: String(page), page_size: String(pageSize) });
  if (assetClass) params.set("asset_class", assetClass);
  if (minMarketCap != null) params.set("min_market_cap", String(minMarketCap));
  if (maxMarketCap != null) params.set("max_market_cap", String(maxMarketCap));
  if (exchange) params.set("exchange", exchange);
  if (region) params.set("region", region);
  if (sector) params.set("sector", sector);
  if (industry) params.set("industry", industry);
  return /** @type {Promise<SearchResponse>} */ (api(`/market/search/?${params.toString()}`));
}

/**
 * @typedef {Object} MarketProfile
 * @property {string} ticker
 * @property {string} name
 * @property {string} quote_type
 * @property {string} exchange
 * @property {string} currency
 * @property {string|null} description
 * @property {string|null} sector
 * @property {string|null} industry
 * @property {string|null} website
 * @property {number|null} beta
 * @property {number|null} payout_ratio
 * @property {number|null} dividend_rate
 * @property {number|null} dividend_yield
 * @property {string|null} dividend_frequency
 * @property {number|null} market_cap
 * @property {number|null} volume
 * @property {number|null} day_open
 * @property {number|null} day_high
 * @property {number|null} day_low
 * @property {number|null} day_close
 * @property {number|null} year_open
 * @property {number|null} year_high
 * @property {number|null} year_low
 * @property {number|null} year_close
 * @property {string|null} address
 * @property {string|null} country
 * @property {string|null} region
 * @property {number|null} full_time_employees
 * @property {{name: string, role: string}[]} ceos
 * @property {string|null} ipo_date
 * @property {string} last_updated
 * @property {string} source
 */

/**
 * GET /api/market/<asset_class>/<symbol>/profile/ — see
 * backend/market_data/views.py's ProfileView. Throws an ApiError with
 * status 404 (see client.js) when no data is published yet for this
 * symbol — callers should catch that and degrade gracefully rather than
 * treating it as a hard failure (see HoldingTickerPage.jsx).
 *
 * Cached in IndexedDB per `assetClass`/`symbol` for the rest of the
 * browser's local calendar day (see utils/profileCache.js) — same
 * rationale as getPrices below. A cache miss/failure (including no
 * IndexedDB support at all) just falls through to the network call; a 404
 * is never cached, so a symbol that hasn't published yet is re-checked on
 * every call.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {Promise<MarketProfile>}
 */
export async function getProfile(api, assetClass, symbol) {
  const cacheKey = profileCacheKey(assetClass, symbol);

  const cached = await readCachedProfile(cacheKey);
  if (cached) return cached;

  const result = /** @type {MarketProfile} */ (await api(`/market/${assetClass}/${symbol}/profile/`));
  writeCachedProfile(cacheKey, result);
  return result;
}

/**
 * @typedef {Object} MarketMetrics
 * @property {number|null} volatility - annualized std deviation of daily
 *   returns, as a fraction (e.g. 0.23 for 23%).
 * @property {number|null} sharpe_ratio
 * @property {number|null} max_drawdown - largest peak-to-trough decline, as
 *   a negative fraction (e.g. -0.25).
 * @property {number|null} cagr_1y
 * @property {number|null} cagr_2y
 * @property {number|null} cagr_3y
 * @property {number|null} cagr_5y
 * @property {number|null} cagr_10y
 * @property {number|null} [pe_ratio] - stock-only; absent for etf/fx (see
 *   equicast_metrics.MetricsClient.fundamentals). Always the plain current
 *   price ÷ trailing EPS calculation — unlike `trailing_pe`, never
 *   yfinance's own reported P/E, so the two can differ.
 * @property {number|null} [trailing_pe]
 * @property {number|null} [forward_pe]
 * @property {number|null} [trailing_eps]
 * @property {number|null} [forward_eps]
 * @property {number|null} [peg]
 * @property {number|null} [price_to_book]
 * @property {number|null} [price_to_sales]
 * @property {number|null} [ev_ebitda]
 * @property {number|null} [gross_margin] - fraction (e.g. 0.42 for 42%).
 * @property {number|null} [operating_margin] - fraction.
 * @property {number|null} [profit_margin] - fraction.
 * @property {number|null} [return_on_equity] - fraction.
 * @property {number|null} [return_on_assets] - fraction.
 * @property {number|null} [debt_to_equity] - already a percentage (e.g.
 *   150.0 for 150%), not a fraction.
 * @property {number|null} [free_cash_flow_per_share]
 * @property {string} last_updated
 * @property {string} source
 */

/**
 * GET /api/market/<asset_class>/<symbol>/metrics/ — see
 * backend/market_data/views.py's MetricsView. Throws an ApiError with
 * status 404 when no `metrics.parquet` is published yet for this symbol —
 * callers should catch that and degrade gracefully, same as getProfile.
 * etf/fx records only ever carry the generic risk/performance fields
 * (`volatility`/`sharpe_ratio`/`max_drawdown`/`cagr_*`); a stock's record
 * additionally carries the valuation/fundamental fields (`trailing_pe`,
 * etc.) — see MarketMetrics.
 *
 * Cached in IndexedDB per `assetClass`/`symbol` for the rest of the
 * browser's local calendar day (see utils/metricsCache.js), same rationale
 * as getProfile/getPrices. A cache miss/failure (including no IndexedDB
 * support at all) just falls through to the network call; a 404 is never
 * cached, so a symbol that hasn't published yet is re-checked on every call.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {Promise<MarketMetrics>}
 */
export async function getMetrics(api, assetClass, symbol) {
  const cacheKey = metricsCacheKey(assetClass, symbol);

  const cached = await readCachedMetrics(cacheKey);
  if (cached) return cached;

  const result = /** @type {MarketMetrics} */ (await api(`/market/${assetClass}/${symbol}/metrics/`));
  writeCachedMetrics(cacheKey, result);
  return result;
}

/**
 * @typedef {Object} DividendRecord
 * @property {string} ticker
 * @property {string} currency
 * @property {string} ex_dividend_date
 * @property {string|null} payment_date - only ever set for a `"declared"`
 *   record, and even then only when yfinance has reported one yet.
 * @property {number} price - per-share cash amount, in `currency`.
 * @property {"paid"|"declared"|"estimated"} status - `"paid"`: an
 *   already-happened payout. `"declared"`: a real, yfinance-confirmed
 *   upcoming payout (0 or 1 of these ever exist for a ticker at a time).
 *   `"estimated"`: a computed projection from historical cadence/growth,
 *   `source: "equicast"` rather than `"yfinance"`.
 * @property {string} last_updated
 * @property {string} source
 */

/**
 * @typedef {Object} DividendsResponse
 * @property {string} ticker
 * @property {string} currency
 * @property {string} last_updated
 * @property {DividendRecord[]} dividends - chronological (ascending
 *   `ex_dividend_date`), unfiltered by date and not deduplicated where a
 *   `"declared"` and an `"estimated"` record estimate the same real-world
 *   payout — see backend/market_data/views.py's DividendsView docstring.
 */

/**
 * GET /api/market/<asset_class>/<symbol>/dividends/ — see
 * backend/market_data/views.py's DividendsView. Throws an ApiError with
 * status 404 when no dividend data (paid, declared, or estimated) is
 * published yet for this symbol — callers should catch that and degrade
 * gracefully, same as getProfile/getMetrics.
 *
 * Cached in IndexedDB per `assetClass`/`symbol` for the rest of the
 * browser's local calendar day (see utils/dividendsCache.js), same
 * rationale as getProfile/getMetrics/getPrices.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {Promise<DividendsResponse>}
 */
export async function getDividends(api, assetClass, symbol) {
  const cacheKey = dividendsCacheKey(assetClass, symbol);

  const cached = await readCachedDividends(cacheKey);
  if (cached) return cached;

  const result = /** @type {DividendsResponse} */ (
    await api(`/market/${assetClass}/${symbol}/dividends/`)
  );
  writeCachedDividends(cacheKey, result);
  return result;
}

/** Badge `tone` (see components/core/Badge.jsx) for each MarketProfile field
 * shown as a badge — one shared mapping so Exchange/Quote type/Synced read
 * the same color wherever a page surfaces them (today: HoldingTickerPage's
 * title badges), rather than each caller picking its own. */
export const MARKET_PROFILE_BADGE_TONES = {
  exchange: "neutral",
  quoteType: "accent",
  synced: "info",
};

/**
 * Every range GET .../prices/'s `?range=` accepts, in the order a range
 * picker should offer them — mirrors equicast_core.client.PRICE_RANGES
 * exactly; keep the two in sync if either changes.
 */
export const PRICE_RANGES = ["1d", "5d", "1m", "6m", "ytd", "1y", "2y", "3y", "5y", "10y", "max"];

/** The backend's own default when `range` is omitted — see
 * backend/market_data/views.py's PricesView / equicast_core's
 * DEFAULT_PRICE_RANGE. */
export const DEFAULT_PRICE_RANGE = "max";

/**
 * @typedef {Object} PriceBar
 * @property {string} date
 * @property {number} open
 * @property {number} high
 * @property {number} low
 * @property {number} close
 */

/**
 * @typedef {Object} PriceSeries
 * @property {string} ticker
 * @property {string|null} currency
 * @property {string|null} last_updated
 * @property {string|null} source
 * @property {PriceBar[]} prices - ascending/oldest-first. Daily bars for
 *   `range` "6m" or shorter; weekly ("1y"/"2y") or monthly ("3y" and up)
 *   OHLC bars otherwise — see equicast_core.client.get_prices.
 */

/**
 * GET /api/market/<asset_class>/<symbol>/prices/ — see
 * backend/market_data/views.py's PricesView. `range` is one of
 * PRICE_RANGES, defaulting client-side to DEFAULT_PRICE_RANGE ("max") so
 * the request URL and the cache key below always agree on what range was
 * actually asked for.
 *
 * Cached in IndexedDB per `assetClass`/`symbol`/`range` for the rest of
 * the browser's local calendar day (see utils/priceCache.js) — the
 * backend's published price data only changes once a day, so a repeat
 * request for the same range later the same day is served from the cache
 * instead of hitting the API again. A cache miss/failure (including no
 * IndexedDB support at all) just falls through to the network call.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @param {{ range?: string }} [options]
 * @returns {Promise<PriceSeries>}
 */
export async function getPrices(api, assetClass, symbol, { range } = {}) {
  const effectiveRange = range ?? DEFAULT_PRICE_RANGE;
  const cacheKey = priceCacheKey(assetClass, symbol, effectiveRange);

  const cached = await readCachedPrices(cacheKey);
  if (cached) return cached;

  const query = new URLSearchParams({ range: effectiveRange }).toString();
  const result = /** @type {PriceSeries} */ (
    await api(`/market/${assetClass}/${symbol}/prices/?${query}`)
  );
  writeCachedPrices(cacheKey, result);
  return result;
}
