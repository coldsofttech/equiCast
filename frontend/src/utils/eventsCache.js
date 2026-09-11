/**
 * A same-day IndexedDB cache for GET .../events/ responses (see
 * api/market.js's getEvents) — see marketDataCache.js for the shared
 * IndexedDB plumbing/rationale this and priceCache.js/profileCache.js/
 * metricsCache.js/dividendsCache.js all build on.
 */

import { readCachedValue, writeCachedValue } from "./marketDataCache.js";

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function eventsCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:events`;
}

/**
 * @param {string} key - see eventsCacheKey
 * @returns {Promise<import("../api/market.js").EventsResponse|null>}
 *   `null` on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedEvents(key) {
  return /** @type {Promise<import("../api/market.js").EventsResponse|null>} */ (
    readCachedValue(key)
  );
}

/**
 * @param {string} key - see eventsCacheKey
 * @param {import("../api/market.js").EventsResponse} events
 * @returns {Promise<void>}
 */
export function writeCachedEvents(key, events) {
  return writeCachedValue(key, events);
}
