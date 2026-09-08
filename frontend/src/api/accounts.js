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
 * @property {string|null} [name] - present on holdings returned from
 *   /accounts and /pies (both account-direct and pie-nested — see
 *   equicast_core.client.MarketDataClient.enrich_holdings, called from
 *   accounts/views.py and pies/views.py); `null` if the ticker has no
 *   published catalog row yet.
 * @property {string|null} [sector] - `null` for etf/fx or an unpublished
 *   ticker.
 * @property {string|null} [industry] - `null` for etf/fx or an unpublished
 *   ticker.
 * @property {string|null} [website] - feeds AssetIcon's favicon lookup,
 *   `null` for an unpublished ticker.
 * @property {number|null} [current_price_native] - the catalog's latest
 *   published price in the ticker's own currency, `null` for an unpublished
 *   ticker.
 * @property {number|null} [current_price] - `current_price_native` converted
 *   to the user's default_currency using the fx catalog's latest published
 *   rate, `null` if no rate is published for the pair.
 * @property {string|null} [last_updated] - the catalog's own `last_updated`
 *   for this ticker (that ticker's ingestion pipeline's last run, a full
 *   ISO 8601 datetime — see equicast_core.catalog.build_catalog_rows),
 *   `null` for an unpublished ticker.
 */

/**
 * @typedef {Object} Pie
 * @property {string} id
 * @property {string} account_id
 * @property {string} name
 * @property {string} description
 * @property {string|null} [icon] - bare bootstrap-icons name (e.g.
 *   "pie-chart-fill"), `null`/absent for a pie predating this field — see
 *   config/portfolioIcons.js's DEFAULT_PORTFOLIO_ICON for the display
 *   fallback.
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
