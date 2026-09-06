/**
 * A plain (non-expiring) IndexedDB cache for one holding's paginated
 * transactions — see marketDataCache.js for the shared "equicast-cache"
 * IndexedDB plumbing this builds on, and its "transactions" store's
 * freshness model (same as accountsCache.js: undated, since a
 * transaction's own create/update/delete is what should invalidate a
 * cached page, not a calendar-day expiry). Cached per (holdingId, page) —
 * 50 transactions per page by default, matching backend/transactions/
 * views.py's TransactionPagination — so HoldingTickerPage's initial load
 * and the "See all" drawer's later pages don't re-hit the API once a page
 * has already been fetched this session.
 */

import {
  readTransactionsValue,
  writeTransactionsValue,
  deleteTransactionsForHolding as deleteTransactionsForHoldingValue,
} from "./marketDataCache.js";

/**
 * @param {string} holdingId
 * @param {number} page
 * @returns {Promise<import("../api/transactions.js").TransactionPage|null>} `null` on a cache miss or any failure.
 */
export function readCachedTransactionsPage(holdingId, page) {
  return /** @type {Promise<import("../api/transactions.js").TransactionPage|null>} */ (
    readTransactionsValue(`${holdingId}:${page}`)
  );
}

/**
 * @param {string} holdingId
 * @param {number} page
 * @param {import("../api/transactions.js").TransactionPage} value
 * @returns {Promise<void>}
 */
export function writeCachedTransactionsPage(holdingId, page, value) {
  return writeTransactionsValue(`${holdingId}:${page}`, value);
}

/**
 * Call after any create/update/delete against `holdingId`'s transactions —
 * drops every page cached for it (the cheapest correct invalidation) so the
 * next read goes back to the API instead of serving a stale page.
 *
 * @param {string} holdingId
 * @returns {Promise<void>}
 */
export function clearCachedTransactionsForHolding(holdingId) {
  return deleteTransactionsForHoldingValue(holdingId);
}
