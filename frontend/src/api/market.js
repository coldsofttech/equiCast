import { priceCacheKey, readCachedPrices, writeCachedPrices } from "../utils/priceCache.js";

/**
 * @typedef {Object} SearchResult
 * @property {string} ticker
 * @property {string} name
 * @property {"stock"|"etf"|"fx"} type
 * @property {number|null} current_price
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
 * fx), used by TickerSearchField to let a caller pick a real ticker rather
 * than typing one blind. Triggered explicitly (Enter/a Search click), not
 * on every keystroke — see TickerSearchField.jsx. `assetClass` narrows the
 * search to one catalog (e.g. "fx" when resolving a currency-pair ticker
 * for FX conversion — see holdings/holdingFinancials.js's resolveFxRate);
 * omitted, it searches every asset class, unchanged from before.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} query
 * @param {{ pageSize?: number, assetClass?: "stock"|"etf"|"fx" }} [options]
 * @returns {Promise<SearchResponse>}
 */
export function searchTickers(api, query, { pageSize = 10, assetClass } = {}) {
  const params = new URLSearchParams({ q: query, page_size: String(pageSize) });
  if (assetClass) params.set("asset_class", assetClass);
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
 * @property {number|null} market_cap
 * @property {number|null} volume
 * @property {number|null} day_open
 * @property {number|null} day_high
 * @property {number|null} day_low
 * @property {number|null} day_close
 * @property {number|null} day_average
 * @property {number|null} year_open
 * @property {number|null} year_high
 * @property {number|null} year_low
 * @property {number|null} year_close
 * @property {number|null} year_average
 * @property {number|null} moving_average_50_days
 * @property {number|null} moving_average_200_days
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
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {Promise<MarketProfile>}
 */
export function getProfile(api, assetClass, symbol) {
  return /** @type {Promise<MarketProfile>} */ (api(`/market/${assetClass}/${symbol}/profile/`));
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
