/**
 * A same-day IndexedDB cache for GET .../prices/ responses (see
 * api/market.js's getPrices) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and profileCache.js/metricsCache.js
 * all build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @param {string} range
 * @returns {string}
 */
export function priceCacheKey(assetClass, symbol, range) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:prices:${range}`;
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
