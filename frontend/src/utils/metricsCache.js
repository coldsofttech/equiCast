/**
 * A same-day IndexedDB cache for GET .../metrics/ responses (see
 * api/market.js's getMetrics) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and priceCache.js/profileCache.js all
 * build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function metricsCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:metrics`;
}

/**
 * @param {string} key - see metricsCacheKey
 * @returns {Promise<import("../api/market.js").MarketMetrics|null>} `null`
 *   on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedMetrics(key) {
  return /** @type {Promise<import("../api/market.js").MarketMetrics|null>} */ (readCachedValue(key));
}

/**
 * @param {string} key - see metricsCacheKey
 * @param {import("../api/market.js").MarketMetrics} metrics
 * @returns {Promise<void>}
 */
export function writeCachedMetrics(key, metrics) {
  return writeCachedValue(key, metrics);
}
