/**
 * @typedef {Object} Holding
 * @property {string} id
 * @property {string} ticker
 * @property {string} asset_class
 * @property {string|null} account_id
 * @property {string|null} pie_id
 * @property {string|null} watchlist_id
 * @property {string} [allocation_pct]
 */

/**
 * @typedef {Object} Pie
 * @property {string} id
 * @property {string} account_id
 * @property {string} name
 * @property {string} description
 * @property {Holding[]} [holdings]
 */

/**
 * @typedef {Object} Account
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {string} account_type
 * @property {string} currency
 * @property {"AVERAGE"|"TRANSACTION"} transaction_type
 * @property {Pie[]} [pies]
 * @property {Holding[]} [holdings]
 */

/**
 * GET /api/accounts/ — see backend/accounts/views.py's AccountListView.get.
 * Each account comes back nested with its pies (each carrying its own
 * holdings) and its own direct holdings.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @returns {Promise<Account[]>}
 */
export function listAccounts(api) {
  return /** @type {Promise<Account[]>} */ (api("/accounts/"));
}

/**
 * GET /api/accounts/<id>/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} accountId
 * @returns {Promise<Account>}
 */
export function getAccount(api, accountId) {
  return /** @type {Promise<Account>} */ (api(`/accounts/${accountId}/`));
}

/**
 * POST /api/accounts/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ name: string, description: string, account_type: string, currency: string, transaction_type: "AVERAGE"|"TRANSACTION" }} data
 * @returns {Promise<Account>}
 */
export function createAccount(api, data) {
  return /** @type {Promise<Account>} */ (api("/accounts/", { method: "POST", body: data }));
}

/**
 * PATCH /api/accounts/<id>/ — `fields` only needs to carry what's changing;
 * REQUIRED_CREATE_FIELDS doesn't apply to updates.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} accountId
 * @param {Partial<{ name: string, description: string, account_type: string, currency: string, transaction_type: "AVERAGE"|"TRANSACTION" }>} fields
 * @returns {Promise<Account>}
 */
export function updateAccount(api, accountId, fields) {
  return /** @type {Promise<Account>} */ (
    api(`/accounts/${accountId}/`, { method: "PATCH", body: fields })
  );
}

/**
 * DELETE /api/accounts/<id>/ — `force: true` cascades through the
 * account's pies and direct holdings (and their transactions); without it,
 * a non-empty account 409s.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} accountId
 * @param {{ force?: boolean }} [options]
 * @returns {Promise<null>}
 */
export function deleteAccount(api, accountId, { force = false } = {}) {
  const query = force ? "?force=true" : "";
  return /** @type {Promise<null>} */ (
    api(`/accounts/${accountId}/${query}`, { method: "DELETE" })
  );
}
