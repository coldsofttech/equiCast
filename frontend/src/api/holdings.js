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
 * GET /api/holdings/<id>/ — see backend/holdings/views.py's
 * HoldingDetailView.get. Used to re-fetch a holding's rollup fields
 * (no_of_shares/average_price_native/average_price/invested_native/invested/
 * dividends_native — see equicast_core.transactions.compute_holding_rollup)
 * right after a
 * transaction create/update/delete against it, so HoldingTickerPage's stats
 * reflect the mutation without a full accounts refetch.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @returns {Promise<Holding>}
 */
export function getHolding(api, holdingId) {
  return /** @type {Promise<Holding>} */ (api(`/holdings/${holdingId}/`));
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
