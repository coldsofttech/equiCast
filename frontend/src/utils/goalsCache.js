/**
 * A plain (non-expiring) IndexedDB cache for the signed-in user's goals
 * list — see marketDataCache.js for the shared "equicast-cache" IndexedDB
 * plumbing this builds on, and its "goals" store's freshness model.
 * One fixed key: there's only ever one goals list to cache per signed-in
 * user on this browser.
 */

import { readGoalsValue, writeGoalsValue, deleteGoalsValue } from "./marketDataCache.js";

const GOALS_KEY = "list";

/**
 * @returns {Promise<import("../api/goals.js").Goal[]|null>} `null` on a
 *   cache miss or any failure.
 */
export function readCachedGoals() {
  return /** @type {Promise<import("../api/goals.js").Goal[]|null>} */ (readGoalsValue(GOALS_KEY));
}

/**
 * @param {import("../api/goals.js").Goal[]} goals
 * @returns {Promise<void>}
 */
export function writeCachedGoals(goals) {
  return writeGoalsValue(GOALS_KEY, goals);
}

/**
 * Call on sign-out so a different account signing in on the same browser
 * doesn't see the previous user's cached goals.
 *
 * @returns {Promise<void>}
 */
export function clearCachedGoals() {
  return deleteGoalsValue(GOALS_KEY);
}
