/**
 * A same-day IndexedDB cache for GET .../profile/ responses (see
 * api/market.js's getProfile) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and priceCache.js/metricsCache.js all
 * build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function profileCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:profile`;
}

/**
 * @param {string} key - see profileCacheKey
 * @returns {Promise<import("../api/market.js").MarketProfile|null>} `null`
 *   on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedProfile(key) {
  return /** @type {Promise<import("../api/market.js").MarketProfile|null>} */ (readCachedValue(key));
}

/**
 * @param {string} key - see profileCacheKey
 * @param {import("../api/market.js").MarketProfile} profile
 * @returns {Promise<void>}
 */
export function writeCachedProfile(key, profile) {
  return writeCachedValue(key, profile);
}
