/**
 * @typedef {import("./accounts.js").Pie} Pie
 * @typedef {import("./accounts.js").Holding} Holding
 */

/**
 * GET /api/pies/?account_id=<id> — see backend/pies/views.py's
 * PieListView.get. `accountId` is optional; omit it for every pie the
 * caller owns.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ accountId?: string }} [options]
 * @returns {Promise<Pie[]>}
 */
export function listPies(api, { accountId } = {}) {
  const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
  return /** @type {Promise<Pie[]>} */ (api(`/pies/${query}`));
}

/**
 * GET /api/pies/<id>/ — nested with its holdings.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} pieId
 * @returns {Promise<Pie>}
 */
export function getPie(api, pieId) {
  return /** @type {Promise<Pie>} */ (api(`/pies/${pieId}/`));
}

/**
 * POST /api/pies/
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ name: string, description: string, account_id: string }} data
 * @returns {Promise<Pie>}
 */
export function createPie(api, data) {
  return /** @type {Promise<Pie>} */ (api("/pies/", { method: "POST", body: data }));
}

/**
 * PATCH /api/pies/<id>/ — only `name`/`description` are updatable;
 * `account_id` is immutable after creation.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} pieId
 * @param {Partial<{ name: string, description: string }>} fields
 * @returns {Promise<Pie>}
 */
export function updatePie(api, pieId, fields) {
  return /** @type {Promise<Pie>} */ (api(`/pies/${pieId}/`, { method: "PATCH", body: fields }));
}

/**
 * DELETE /api/pies/<id>/ — `force: true` cascades through the pie's
 * holdings (and their transactions); without it, a non-empty pie 409s.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} pieId
 * @param {{ force?: boolean }} [options]
 * @returns {Promise<null>}
 */
export function deletePie(api, pieId, { force = false } = {}) {
  const query = force ? "?force=true" : "";
  return /** @type {Promise<null>} */ (api(`/pies/${pieId}/${query}`, { method: "DELETE" }));
}

/**
 * PUT /api/pies/<id>/holdings/ — the only way to mutate a pie's holdings;
 * see backend/pies/views.py's PieHoldingsView.put. `allocation_pct` values
 * are sent as strings so JS number handling never touches them before the
 * backend's `Decimal(str(value))` parse does — see
 * equicast_core.holdings._validate_allocation.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} pieId
 * @param {{
 *   add?: { ticker: string, asset_class: string, allocation_pct: string }[],
 *   remove?: string[],
 *   reallocate?: { id: string, allocation_pct: string }[],
 * }} batch
 * @returns {Promise<Pie & { holdings: Holding[] }>}
 */
export function syncPieHoldings(api, pieId, batch) {
  return /** @type {Promise<Pie & { holdings: Holding[] }>} */ (
    api(`/pies/${pieId}/holdings/`, { method: "PUT", body: batch })
  );
}
