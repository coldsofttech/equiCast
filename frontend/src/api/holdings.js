/**
 * @typedef {import("./accounts.js").Holding} Holding
 */

/**
 * POST /api/holdings/ — see backend/holdings/views.py's HoldingListView.post.
 * Only account-direct holdings are created this way from the frontend so
 * far (pie holdings go through pies.js's syncPieHoldings instead, since a
 * pie's holdings must always sum to exactly 100% allocation — a plain
 * single-item create can't maintain that).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ ticker: string, asset_class: string, account_id: string }} data
 * @returns {Promise<Holding>}
 */
export function createHolding(api, data) {
  return /** @type {Promise<Holding>} */ (api("/holdings/", { method: "POST", body: data }));
}

/**
 * DELETE /api/holdings/<id>/ — also cascades to delete any transactions
 * recorded against this holding (see backend/holdings/views.py's
 * HoldingDetailView.delete).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @returns {Promise<null>}
 */
export function deleteHolding(api, holdingId) {
  return /** @type {Promise<null>} */ (api(`/holdings/${holdingId}/`, { method: "DELETE" }));
}
