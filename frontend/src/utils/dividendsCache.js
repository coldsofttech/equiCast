/**
 * A same-day IndexedDB cache for GET .../dividends/ responses (see
 * api/market.js's getDividends) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and priceCache.js/profileCache.js/
 * metricsCache.js all build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function dividendsCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:dividends`;
}

/**
 * @param {string} key - see dividendsCacheKey
 * @returns {Promise<import("../api/market.js").DividendsResponse|null>}
 *   `null` on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedDividends(key) {
  return /** @type {Promise<import("../api/market.js").DividendsResponse|null>} */ (
    readCachedValue(key)
  );
}

/**
 * @param {string} key - see dividendsCacheKey
 * @param {import("../api/market.js").DividendsResponse} dividends
 * @returns {Promise<void>}
 */
export function writeCachedDividends(key, dividends) {
  return writeCachedValue(key, dividends);
}
