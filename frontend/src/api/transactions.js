/**
 * Every monetary field comes in a native/converted pair: `*_native` is
 * exactly what the caller submitted (the holding's own native currency);
 * the bare name is that figure converted to the user's own
 * `default_currency` (see identity.js's UserProfile) as of the
 * transaction's `date`, using `fx_rate` — resolved server-side via the
 * historical FX rate for that date by default, or the caller's own
 * override (GitHub issue #149 — submit `fx_rate` to use it instead of the
 * auto-resolved one; see `createTransaction`/`updateTransaction`) —
 * `null` when no rate could be resolved (e.g. no FX pair published for
 * that currency combination on or before that date). Never submit a bare
 * converted field (`average_price`/`price`/`amount`) yourself — the
 * backend always rejects it as a request field; only the `*_native`
 * fields and `fx_rate` are ever writable.
 *
 * @typedef {Object} Transaction
 * @property {string} id
 * @property {string} holding_id
 * @property {number|null} no_of_shares - set only for a BUY/SELL record.
 * @property {number|null} average_price_native - set only for an AVERAGE-mode BUY record.
 * @property {number|null} average_price - converted counterpart of average_price_native.
 * @property {number|null} price_native - set only for a TRANSACTION-mode BUY/SELL record.
 * @property {number|null} price - converted counterpart of price_native.
 * @property {number|null} amount_native - total cash received, set only for a DIVIDEND record.
 * @property {number|null} amount - converted counterpart of amount_native.
 * @property {number|null} fx_rate - the effective rate used to resolve every converted field
 *   above, whether auto-resolved or overridden — always present regardless of type, `null`
 *   when it couldn't be resolved.
 * @property {string|null} date - "YYYY-MM-DD". Mandatory on every record created since the
 *   DIVIDEND type shipped; `null` only on a legacy AVERAGE-mode record predating it.
 * @property {"BUY"|"SELL"|"DIVIDEND"|null} type - "SELL" only under a TRANSACTION-mode
 *   account; `null` only on a legacy AVERAGE-mode record predating the BUY/DIVIDEND shape.
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * One page of `GET /api/transactions/` — DRF's standard page-number
 * pagination envelope (see backend/transactions/views.py's
 * TransactionPagination). `results` is sorted most-recent-`date`-first by
 * the backend, so page 1 is always what a "recent transactions" pane wants.
 *
 * @typedef {Object} TransactionPage
 * @property {number} count - total transactions matching the filter, across every page.
 * @property {string|null} next - the next page's URL, `null` on the last page.
 * @property {string|null} previous - the previous page's URL, `null` on the first page.
 * @property {Transaction[]} results - this page's transactions (`pageSize` items, default 50).
 */

/**
 * GET /api/transactions/?holding_id=...&page=...&page_size=... — see
 * backend/transactions/views.py's TransactionListView.get. Defaults to page
 * 1 at 50 per page (TransactionPagination.page_size) when `page`/`pageSize`
 * are omitted. Omitting `holdingId` returns every transaction across all of
 * the caller's holdings (an uncommon, slower path server-side — see
 * TransactionsClient._load_all) rather than the one this holding detail
 * page actually needs.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ holdingId?: string, year?: number|string, dateFrom?: string, dateTo?: string, page?: number, pageSize?: number }} [options]
 * @returns {Promise<TransactionPage>}
 */
export function listTransactions(api, { holdingId, year, dateFrom, dateTo, page, pageSize } = {}) {
  const params = new URLSearchParams();
  if (holdingId) params.set("holding_id", holdingId);
  if (year) params.set("year", String(year));
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (page) params.set("page", String(page));
  if (pageSize) params.set("page_size", String(pageSize));
  const query = params.toString();
  return /** @type {Promise<TransactionPage>} */ (api(`/transactions/${query ? `?${query}` : ""}`));
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
 * POST /api/transactions/ — `data`'s shape depends on the user's global
 * transaction_type and `data.type`: an AVERAGE-mode BUY needs
 * `{holding_id, type: "BUY", no_of_shares, average_price_native, date}`; a
 * TRANSACTION-mode BUY/SELL needs `{holding_id, type, no_of_shares,
 * price_native, date}`; a DIVIDEND (either mode) needs `{holding_id,
 * type: "DIVIDEND", amount_native, date}` (see
 * backend/transactions/views.py's build_transaction_fields). The
 * converted (non-`_native`) counterpart is always backend-resolved — never
 * submit it, see the Transaction typedef above. `fx_rate` is optional on
 * every type — omit it to auto-resolve the historical rate for `date`, or
 * supply it to override that resolution (GitHub issue #149).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ holding_id: string, type: "BUY"|"SELL"|"DIVIDEND", date: string, no_of_shares?: number, average_price_native?: number, price_native?: number, amount_native?: number, fx_rate?: number }} data
 * @returns {Promise<Transaction>}
 */
export function createTransaction(api, data) {
  return /** @type {Promise<Transaction>} */ (
    api("/transactions/", { method: "POST", body: data })
  );
}

/**
 * PATCH /api/transactions/<holding_id>/<transaction_id>/ — only valid for
 * an AVERAGE-mode BUY record (`no_of_shares`/`average_price_native`/
 * `fx_rate`/`date`) or any DIVIDEND record in either mode (`date`/
 * `amount_native`/`fx_rate`); a TRANSACTION-mode BUY/SELL record is
 * immutable server-side. The converted counterpart is recomputed
 * server-side whenever a native value, `date`, or `fx_rate` changes —
 * never submit it yourself. Omitting `fx_rate` from a patch that does
 * change the native value/date re-auto-resolves the rate fresh rather
 * than keeping an earlier override (GitHub issue #149) — resubmit
 * `fx_rate` alongside such a patch to keep a prior override.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} holdingId
 * @param {string} transactionId
 * @param {{ no_of_shares?: number, average_price_native?: number, date?: string, amount_native?: number, fx_rate?: number }} fields
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
