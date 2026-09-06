/**
 * A plain (non-expiring) IndexedDB cache for the signed-in user's accounts
 * list — see marketDataCache.js for the shared "equicast-cache" IndexedDB
 * plumbing this builds on, and its "accounts" store's freshness model.
 * One fixed key: there's only ever one accounts list to cache per signed-in
 * user on this browser.
 */

import { readAccountsValue, writeAccountsValue, deleteAccountsValue } from "./marketDataCache.js";

const ACCOUNTS_KEY = "list";

/**
 * @returns {Promise<import("../api/accounts.js").Account[]|null>} `null` on
 *   a cache miss or any failure.
 */
export function readCachedAccounts() {
  return /** @type {Promise<import("../api/accounts.js").Account[]|null>} */ (readAccountsValue(ACCOUNTS_KEY));
}

/**
 * @param {import("../api/accounts.js").Account[]} accounts
 * @returns {Promise<void>}
 */
export function writeCachedAccounts(accounts) {
  return writeAccountsValue(ACCOUNTS_KEY, accounts);
}

/**
 * Call on sign-out so a different account signing in on the same browser
 * doesn't see the previous user's cached accounts.
 *
 * @returns {Promise<void>}
 */
export function clearCachedAccounts() {
  return deleteAccountsValue(ACCOUNTS_KEY);
}
