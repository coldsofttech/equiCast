/**
 * @typedef {Object} Goal
 * @property {string} id
 * @property {string} name
 * @property {"buy_home"|"buy_car"|"holiday"|"emergency_fund"|"retirement"|"education"|"wedding"|"other"} purpose
 * @property {string|null} custom_purpose - required by the backend when
 *   `purpose` is "other" (see config/goalPurposes.js), `null` otherwise.
 * @property {number} target_amount - always interpreted in the user's
 *   *current* `default_currency` (see useCurrentUser) — a goal has no
 *   currency of its own (see pages/goals/goalFinancials.js).
 * @property {string|null} target_date - "YYYY-MM-DD", optional.
 * @property {string[]} account_ids - accounts mapped to this goal; an
 *   account/pie can be mapped to at most one goal at a time (backend 409s
 *   otherwise — see backend/goals/views.py).
 * @property {string[]} pie_ids
 * @property {"active"|"achieved"} status - flips to "achieved" once this
 *   goal's live progress reaches its target (see goalFinancials.js's
 *   useGoalAchievementSync) — computed client-side, never by this API.
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * GET /api/goals/ — see backend/goals/views.py's GoalListView.get.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @returns {Promise<Goal[]>}
 */
export function listGoals(api) {
  return /** @type {Promise<Goal[]>} */ (api("/goals/"));
}

/**
 * GET /api/goals/<id>/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} goalId
 * @returns {Promise<Goal>}
 */
export function getGoal(api, goalId) {
  return /** @type {Promise<Goal>} */ (api(`/goals/${goalId}/`));
}

/**
 * POST /api/goals/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ name: string, purpose: string, target_amount: number, custom_purpose?: string, target_date?: string, account_ids?: string[], pie_ids?: string[] }} data
 * @returns {Promise<Goal>}
 */
export function createGoal(api, data) {
  return /** @type {Promise<Goal>} */ (api("/goals/", { method: "POST", body: data }));
}

/**
 * PATCH /api/goals/<id>/ — `fields` only needs to carry what's changing.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} goalId
 * @param {Partial<{ name: string, purpose: string, custom_purpose: string, target_amount: number, target_date: string, account_ids: string[], pie_ids: string[], status: string }>} fields
 * @returns {Promise<Goal>}
 */
export function updateGoal(api, goalId, fields) {
  return /** @type {Promise<Goal>} */ (api(`/goals/${goalId}/`, { method: "PATCH", body: fields }));
}

/**
 * DELETE /api/goals/<id>/ — goals have no nested children, so unlike
 * accounts/pies/watchlists there's no `force` option.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} goalId
 * @returns {Promise<null>}
 */
export function deleteGoal(api, goalId) {
  return /** @type {Promise<null>} */ (api(`/goals/${goalId}/`, { method: "DELETE" }));
}
