/**
 * A same-day IndexedDB cache for GET .../prices/ responses (see
 * api/market.js's getPrices) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and profileCache.js/metricsCache.js
 * all build on.
 *
 * One entry per ticker, not per ticker+range — getPrices always fetches
 * the same bundled `{daily, weekly, monthly}` payload regardless of which
 * range the user has picked (see GitHub issue #150), so there's only ever
 * one thing to cache per ticker.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function priceCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:prices`;
}

/**
 * @param {string} key - see priceCacheKey
 * @returns {Promise<import("../api/market.js").PriceSeries|null>} `null`
 *   on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedPrices(key) {
  return /** @type {Promise<import("../api/market.js").PriceSeries|null>} */ (readCachedValue(key));
}

/**
 * @param {string} key - see priceCacheKey
 * @param {import("../api/market.js").PriceSeries} series
 * @returns {Promise<void>}
 */
export function writeCachedPrices(key, series) {
  return writeCachedValue(key, series);
}
