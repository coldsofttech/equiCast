/**
 * Login-time FX warm-up (GitHub issue #149): once the user's profile has
 * loaded, silently pre-read each of `profile.fx_warmup_currencies`' pairs
 * (against `profile.default_currency`) into the backend's process-wide
 * parquet cache (see equicast_core.client's `_read_parquet` cache,
 * `MarketDataClient.get_fx_rate_on_date`), so a later real transaction's
 * historical-rate lookup — for some other, arbitrary date — is served from
 * that same already-cached file instead of a fresh S3 read. Fire-and-forget:
 * no loading state, no UI, failures are silently swallowed.
 *
 * Session-scoped guard mirrors api/useCurrentUser.js's sessionCache
 * pattern (a fixed key, checked/set once) so this only actually fires once
 * per tab session — `warmFxRates` itself is cheap to call from more than
 * one mount (e.g. every page that happens to call it), only the first call
 * this session does any work.
 */

import { getFxRateOnDate } from "../api/market.js";
import { readCache, writeCache } from "../api/sessionCache.js";

const CACHE_KEY = "ec_fx_warmed";

/** Today's date as "YYYY-MM-DD" (UTC) — any recent date works equally well
 * for warming purposes, since a fx pair's whole parquet file is what gets
 * cached, not a value keyed to this exact date. */
function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {import("../api/identity.js").UserProfile|null} profile
 */
export function warmFxRates(api, profile) {
  if (!profile) return;
  if (readCache(CACHE_KEY)) return;
  writeCache(CACHE_KEY, true);

  const date = todayIso();
  (profile.fx_warmup_currencies ?? [])
    .filter((currency) => currency !== profile.default_currency)
    .forEach((currency) => {
      // default→native, matching the direction the transaction form's own
      // FX rate field now fetches/displays (a rate like "£1 = $xxx" — see
      // HoldingTransactionsSection.jsx's TransactionForm) — warming the
      // same direction that request will actually try first, rather than
      // relying on get_fx_rate_on_date's own direct/inverted-pair fallback
      // to land on the same cached file regardless.
      getFxRateOnDate(api, profile.default_currency, currency, date).catch(() => {
        // Best-effort — see module docstring. A 404 (nothing published for
        // this pair) or a network failure just means this warm-up attempt
        // didn't help; it never blocks or surfaces to the caller.
      });
    });
}
