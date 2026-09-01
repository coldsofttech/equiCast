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
 * on every keystroke — see TickerSearchField.jsx.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} query
 * @param {{ pageSize?: number }} [options]
 * @returns {Promise<SearchResponse>}
 */
export function searchTickers(api, query, { pageSize = 10 } = {}) {
  const params = new URLSearchParams({ q: query, page_size: String(pageSize) });
  return /** @type {Promise<SearchResponse>} */ (api(`/market/search/?${params.toString()}`));
}
