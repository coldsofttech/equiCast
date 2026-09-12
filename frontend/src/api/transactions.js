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

/**
 * One imported BUY/SELL row, as returned by `previewImport` and echoed
 * back (verbatim, or with the user's edits) as part of a `commitImport`
 * selection's `rows`.
 *
 * @typedef {Object} ImportRow
 * @property {string|null} external_id - the broker's own row/order id when the source
 *   provides one (e.g. Trading 212's `ID` column) — used server-side to skip an
 *   already-imported row on a repeat upload (TRANSACTION mode only).
 * @property {string} date - "YYYY-MM-DD".
 * @property {"BUY"|"SELL"} type
 * @property {number} no_of_shares
 * @property {number} price_native
 * @property {number|null} fx_rate - the source's own per-row exchange rate when provided,
 *   else equicast's own historical FX rate resolved for `date` — `null` if neither resolved.
 */

/**
 * One ticker equicast could match against an existing holding, as returned
 * by `previewImport`.
 *
 * @typedef {Object} ImportExistingHolding
 * @property {string} id
 * @property {string|null} account_id
 * @property {string|null} account_name
 * @property {string|null} pie_id
 * @property {boolean} already_has_position - AVERAGE mode only: true if this holding
 *   already has a BUY on record, so committing into it *extends* the position rather
 *   than creating a new one — see `combined_preview`.
 * @property {{no_of_shares: number, average_price_native: number|null, average_price: number|null}|null} combined_preview -
 *   only set when `already_has_position` is true: the resulting position if the import
 *   is committed against this holding.
 * @property {number} duplicate_count - TRANSACTION mode: how many of this group's rows
 *   already exist on this holding (matched by `external_id`) and would be skipped.
 */

/**
 * One ticker group parsed from the uploaded file, as returned by
 * `previewImport`.
 *
 * @typedef {Object} ImportGroup
 * @property {string} ticker
 * @property {string|null} asset_class - `null` if the ticker didn't resolve against the
 *   market-data catalog (`resolved` is false) — the review screen should let the user
 *   remap it (see `TickerSearchField`).
 * @property {boolean} resolved
 * @property {string|null} name
 * @property {string|null} isin - from the source file, when it carries one (e.g. Trading 212) —
 *   not currently used for matching, see GitHub issue #191.
 * @property {ImportExistingHolding[]} existing_holdings
 * @property {{no_of_shares: number, average_price_native: number|null, average_price: number|null}|null} mode_preview -
 *   the net position this group's rows alone would produce, regardless of target.
 * @property {ImportRow[]} rows
 */

/**
 * @typedef {Object} ImportPreview
 * @property {string} preset
 * @property {"AVERAGE"|"TRANSACTION"} mode
 * @property {number} rows_skipped - rows in the file that weren't BUY/SELL (dividends,
 *   interest, deposits, ...) and were dropped before parsing even reached a ticker group.
 * @property {ImportGroup[]} groups
 */

/**
 * POST /api/transactions/import/preview/ — stateless: parses `file` under
 * `preset` ("generic" or "trading212") and resolves it against the user's
 * holdings/catalog, but creates nothing. See backend/transactions/
 * import_views.py's ImportPreviewView.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {File} file
 * @param {"generic"|"trading212"} preset
 * @returns {Promise<ImportPreview>}
 */
export function previewImport(api, file, preset) {
  const body = new FormData();
  body.set("file", file);
  body.set("preset", preset);
  return /** @type {Promise<ImportPreview>} */ (
    api("/transactions/import/preview/", { method: "POST", body })
  );
}

/**
 * One group's worth of rows to actually import, as sent to `commitImport`.
 *
 * @typedef {Object} ImportSelection
 * @property {string} ticker
 * @property {string} asset_class
 * @property {{type: "existing_holding"|"account"|"pie", id: string, allocation_pct?: number}} target -
 *   `allocation_pct` is required when `type` is "pie" and the pie already has holdings
 *   (equicast computes the first-holding case as 100% itself).
 * @property {ImportRow[]} rows - the checked/edited subset of a group's rows to import.
 */

/**
 * One selection's outcome, as returned by `commitImport`.
 *
 * @typedef {Object} ImportResult
 * @property {string} ticker
 * @property {string|null} holding_id - `null` only when `status` is "error" and the
 *   target itself couldn't be resolved/created.
 * @property {"created"|"partial"|"skipped"|"error"} status
 * @property {number} [created_count]
 * @property {number} [skipped_duplicate_count]
 * @property {{date: string, external_id: string|null, detail: string}[]} [errors] - TRANSACTION
 *   mode only: per-row failures that didn't abort the rest of this selection's rows.
 * @property {string|null} [detail] - a human-readable summary (e.g. "Extended existing
 *   position: 2 -> 5 shares.") or the error message when `status` is "error".
 */

/**
 * POST /api/transactions/import/commit/ — bulk-creates (and, where needed,
 * creates the holdings for) the reviewed `selections`. Each selection is
 * processed independently server-side — one failing never aborts the rest
 * of the batch, see backend/transactions/import_views.py's
 * ImportCommitView.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {ImportSelection[]} selections
 * @returns {Promise<{results: ImportResult[]}>}
 */
export function commitImport(api, selections) {
  return /** @type {Promise<{results: ImportResult[]}>} */ (
    api("/transactions/import/commit/", { method: "POST", body: { selections } })
  );
}
