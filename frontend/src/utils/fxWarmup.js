/**
 * Login-time FX warm-up (GitHub issue #149, IndexedDB caching/loading UI
 * GitHub issue #177): once the user's profile has loaded, pre-fetch each of
 * `profile.fx_warmup_currencies`' pairs' *entire* price history (against
 * `profile.default_currency`) via `getPrices`, the same call
 * holdingFinancials.js's `resolveFxRateOnDate` makes for a real transaction
 * lookup. This warms two caches at once:
 *  - Server-side, the backend's process-wide parquet cache (see
 *    equicast_core.client's `_read_parquet` cache).
 *  - Client-side, `getPrices`' own IndexedDB cache (see priceCache.js,
 *    same-day freshness) — since this fetches the *whole* history in one
 *    request rather than one date at a time, every date a user might later
 *    pick for a transaction is already covered, not just today's.
 *
 * Best-effort: a 404 (nothing published for a pair) or a network failure
 * just means that one warm-up attempt didn't help; never throws.
 *
 * Session-scoped guard mirrors api/useCurrentUser.js's sessionCache
 * pattern (a fixed key, checked/set once) so this only actually fires once
 * per tab session — `warmFxRates` itself is cheap to call from more than
 * one mount (e.g. every page that happens to call it), only the first call
 * this session does any work. Always returns a Promise that resolves once
 * every attempt has settled (including immediately, when already warmed
 * this session or given no profile) — DashboardPage awaits it to know when
 * warm-up has finished, for its own loading screen (see AppLoadingScreen.jsx).
 */

import { getPrices } from "../api/market.js";
import { readCache, writeCache } from "../api/sessionCache.js";

const CACHE_KEY = "ec_fx_warmed";

/**
 * Whether `warmFxRates` has already run (or short-circuited on `null`
 * profile) this tab session — checked synchronously, so a caller like
 * DashboardPage can decide its *initial* loading-screen state without a
 * frame of the wrong answer: `warmFxRates` itself only resolves that same
 * information asynchronously, which would flash a "still loading" state
 * for one render even on a same-session remount where nothing is actually
 * pending. `writeCache` in `warmFxRates` below runs synchronously before
 * its own async work starts, so this is accurate as of the moment it's
 * called, not just eventually.
 *
 * @returns {boolean}
 */
export function hasWarmedFxRates() {
  return Boolean(readCache(CACHE_KEY));
}

/**
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {import("../api/identity.js").UserProfile|null} profile
 * @returns {Promise<void>}
 */
export function warmFxRates(api, profile) {
  if (!profile) return Promise.resolve();
  if (readCache(CACHE_KEY)) return Promise.resolve();
  writeCache(CACHE_KEY, true);

  const pairs = (profile.fx_warmup_currencies ?? []).filter(
    (currency) => currency !== profile.default_currency
  );
  // default→native (e.g. "GBPUSD"), matching the direction
  // resolveFxRateOnDate tries first — warming the same pair that request
  // will actually try first, rather than relying on its own direct/
  // inverted-pair fallback to land on the same cached file regardless.
  return Promise.allSettled(
    pairs.map((currency) => getPrices(api, "fx", `${profile.default_currency}${currency}`))
  ).then(() => undefined);
}
