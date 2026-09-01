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
 * fx). Used by TickerSearchField (a portfolio/account holdings picker,
 * triggered explicitly on Enter/a Search click, not on every keystroke —
 * see TickerSearchField.jsx) and by SearchPage (the full results page,
 * with `assetClass`/`page` for its Type filter and "Load more").
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} query
 * @param {{ assetClass?: "stock"|"etf"|"fx", page?: number, pageSize?: number }} [options]
 * @returns {Promise<SearchResponse>}
 */
export function searchTickers(api, query, { assetClass, page = 1, pageSize = 10 } = {}) {
  const params = new URLSearchParams({ q: query, page: String(page), page_size: String(pageSize) });
  if (assetClass) params.set("asset_class", assetClass);
  return /** @type {Promise<SearchResponse>} */ (api(`/market/search/?${params.toString()}`));
}
