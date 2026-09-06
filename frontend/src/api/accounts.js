/**
 * @typedef {Object} Holding
 * @property {string} id
 * @property {string} ticker
 * @property {string} asset_class
 * @property {string|null} account_id
 * @property {string|null} pie_id
 * @property {string|null} watchlist_id
 * @property {string} [allocation_pct]
 * @property {number} no_of_shares
 * @property {number|null} average_price_native
 * @property {number|null} average_price - converted to the user's default_currency.
 * @property {number} invested_native
 * @property {number} invested - converted to the user's default_currency.
 * @property {number} dividends_native
 * @property {number} dividends - converted to the user's default_currency.
 * @property {string|null} [name] - only present on a pie's nested holdings
 *   (see backend/pies/views.py's `_enrich_holdings`); `null` if the ticker
 *   has no published market profile yet.
 * @property {string|null} [sector] - pie-nested only; `null` for etf/fx or
 *   an unpublished ticker.
 * @property {string|null} [industry] - pie-nested only; `null` for etf/fx or
 *   an unpublished ticker.
 * @property {string|null} [website] - pie-nested only; feeds AssetIcon's
 *   favicon lookup, `null` for an unpublished ticker.
 * @property {number|null} [current_price_native] - pie-nested only; today's
 *   price in the ticker's own currency, `null` for an unpublished ticker.
 * @property {number|null} [current_price] - pie-nested only; `current_price_native`
 *   converted to the user's default_currency, `null` if no FX rate is published.
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
 * @param {{ name: string, description: string, account_type: string, currency: string }} data
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
 * @param {Partial<{ name: string, description: string, account_type: string, currency: string }>} fields
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
