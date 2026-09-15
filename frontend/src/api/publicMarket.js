import { apiFetch } from "./client.js";

/**
 * @typedef {Object} PublicDemoBar
 * @property {string} date - "YYYY-MM-DD"
 * @property {number} open
 * @property {number} high
 * @property {number} low
 * @property {number} close
 */

/**
 * @typedef {Object} PublicDemoTicker
 * @property {string} ticker
 * @property {"stock"|"etf"} asset_class
 * @property {string} name
 * @property {string|null} currency
 * @property {PublicDemoBar[]} prices - ascending/oldest-first, ~1 month of
 *   daily bars.
 */

/**
 * GET /api/market/public/demo-prices/ — see backend/market_data/views.py's
 * PublicDemoPricesView. The *only* unauthenticated market-data endpoint —
 * every other one requires a signed-in caller — so this is called with a
 * plain `apiFetch` directly rather than through `useApi()` (no
 * `getAccessToken`, since the landing page's DemoChart renders before any
 * sign-in has happened). Always returns the same fixed three tickers
 * (AAPL, NVDA, VOO), in that order — there's no per-caller input to this
 * endpoint at all.
 *
 * @returns {Promise<{ tickers: PublicDemoTicker[] }>}
 */
export function getPublicDemoPrices() {
  return /** @type {Promise<{ tickers: PublicDemoTicker[] }>} */ (
    apiFetch("/market/public/demo-prices/")
  );
}
