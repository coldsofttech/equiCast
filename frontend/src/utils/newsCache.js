/**
 * A same-day IndexedDB cache for GET .../news/ responses (see
 * api/market.js's getNews) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and priceCache.js/profileCache.js/
 * metricsCache.js/dividendsCache.js all build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function newsCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:news`;
}

/**
 * @param {string} key - see newsCacheKey
 * @returns {Promise<import("../api/market.js").NewsResponse|null>}
 *   `null` on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedNews(key) {
  return /** @type {Promise<import("../api/market.js").NewsResponse|null>} */ (
    readCachedValue(key)
  );
}

/**
 * @param {string} key - see newsCacheKey
 * @param {import("../api/market.js").NewsResponse} news
 * @returns {Promise<void>}
 */
export function writeCachedNews(key, news) {
  return writeCachedValue(key, news);
}
