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

/**
 * @typedef {Object} PriceRecord
 * @property {string} ticker
 * @property {string} currency
 * @property {string} date
 * @property {number} open
 * @property {number} high
 * @property {number} low
 * @property {number} close
 * @property {number} average
 * @property {string} last_updated
 * @property {string} source
 */

/**
 * GET /api/market/<asset_class>/<symbol>/prices/ — see
 * backend/market_data/views.py's PricesView. Current calendar year only.
 * `results` is ascending/oldest-first (see equicast_stock's writer).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {Promise<{ ticker: string, results: PriceRecord[] }>}
 */
export function getPrices(api, assetClass, symbol) {
  return /** @type {Promise<{ ticker: string, results: PriceRecord[] }>} */ (
    api(`/market/${assetClass}/${symbol}/prices/`)
  );
}
