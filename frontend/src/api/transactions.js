/**
 * @typedef {Object} Transaction
 * @property {string} id
 * @property {string} holding_id
 * @property {number} no_of_shares
 * @property {number|null} average_price - set only for an AVERAGE-mode account's record.
 * @property {number|null} price - set only for a TRANSACTION-mode account's record.
 * @property {string|null} date - "YYYY-MM-DD", set only for a TRANSACTION-mode record.
 * @property {"BUY"|"SELL"|null} type - set only for a TRANSACTION-mode record.
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * GET /api/transactions/?holding_id=... — see backend/transactions/views.py's
 * TransactionListView.get. Omitting `holdingId` returns every transaction
 * across all of the caller's holdings (an uncommon, slower path server-side
 * — see TransactionsClient._load_all) rather than the one this holding
 * detail page actually needs.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ holdingId?: string, year?: number|string, dateFrom?: string, dateTo?: string }} [options]
 * @returns {Promise<Transaction[]>}
 */
export function listTransactions(api, { holdingId, year, dateFrom, dateTo } = {}) {
  const params = new URLSearchParams();
  if (holdingId) params.set("holding_id", holdingId);
  if (year) params.set("year", String(year));
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  return /** @type {Promise<Transaction[]>} */ (api(`/transactions/${query ? `?${query}` : ""}`));
}

/**
 * GET /api/transactions/<holding_id>/<transaction_id>/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @param {string} transactionId
 * @returns {Promise<Transaction>}
 */
export function getTransaction(api, holdingId, transactionId) {
  return /** @type {Promise<Transaction>} */ (
    api(`/transactions/${holdingId}/${transactionId}/`)
  );
}

/**
 * POST /api/transactions/ — `data`'s shape depends on the owning account's
 * transaction_type: AVERAGE mode needs `{holding_id, no_of_shares,
 * average_price}`; TRANSACTION mode needs `{holding_id, no_of_shares,
 * price, date, type}` (see backend/transactions/views.py's
 * build_transaction_fields).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ holding_id: string, no_of_shares: number, average_price?: number, price?: number, date?: string, type?: "BUY"|"SELL" }} data
 * @returns {Promise<Transaction>}
 */
export function createTransaction(api, data) {
  return /** @type {Promise<Transaction>} */ (
    api("/transactions/", { method: "POST", body: data })
  );
}

/**
 * PATCH /api/transactions/<holding_id>/<transaction_id>/ — only valid for
 * an AVERAGE-mode record (`no_of_shares`/`average_price`); a
 * TRANSACTION-mode record is immutable server-side.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @param {string} transactionId
 * @param {{ no_of_shares?: number, average_price?: number }} fields
 * @returns {Promise<Transaction>}
 */
export function updateTransaction(api, holdingId, transactionId, fields) {
  return /** @type {Promise<Transaction>} */ (
    api(`/transactions/${holdingId}/${transactionId}/`, { method: "PATCH", body: fields })
  );
}

/**
 * DELETE /api/transactions/<holding_id>/<transaction_id>/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @param {string} transactionId
 * @returns {Promise<null>}
 */
export function deleteTransaction(api, holdingId, transactionId) {
  return /** @type {Promise<null>} */ (
    api(`/transactions/${holdingId}/${transactionId}/`, { method: "DELETE" })
  );
}
