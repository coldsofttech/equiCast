/**
 * Persists fetched asset-icon images (see websiteIcon.js/AssetIcon.jsx) in
 * IndexedDB as raw `Blob`s, keyed by the resolved icon URL itself — see
 * marketDataCache.js's "icons" store for the storage/TTL rationale. Without
 * this, a plain `<img src>` re-issues a request to Brandfetch/Google on
 * every page load/refresh regardless of the browser's own HTTP cache (see
 * equicast-support#233), since neither third-party service reliably sends
 * long-lived `Cache-Control`.
 *
 * `fetch()` (rather than a plain `<img>`) is what lets this read the
 * response body into a `Blob` at all — but it also means the response has
 * to actually be CORS-readable, which a bare `<img>` load never required.
 * Neither Brandfetch's nor Google's service is guaranteed to send
 * `Access-Control-Allow-Origin`; when it's missing, `fetch()` rejects
 * (indistinguishable from a genuine network failure from JS). `loadIcon`
 * treats that case as "can't cache this one" rather than "this candidate
 * has no icon" — it hands back the plain URL for the caller to load via a
 * normal `<img>` exactly like before this cache existed, so a CORS-blocked
 * provider never regresses below today's behaviour, it just isn't cached.
 * A real "no icon here" response (non-2xx, or a body that isn't an image —
 * e.g. Brandfetch 401s without a valid client ID) returns `null` instead,
 * so AssetIcon's fallback cascade moves on to the next candidate exactly
 * as it does today on an `<img>` load failure.
 */

import { readIconValue, writeIconValue } from "./marketDataCache.js";

/**
 * @typedef {Object} LoadedIcon
 * @property {string} src - an `object URL` (cache hit, or a fetch that was
 *   readable and got cached just now) or the original `url` unchanged (a
 *   fetch that failed for an indeterminate/CORS reason).
 * @property {boolean} isObjectUrl - whether `src` must be revoked with
 *   `URL.revokeObjectURL` once the caller is done with it.
 */

/**
 * @param {string} url - a candidate from resolveIconCandidates.
 * @returns {Promise<LoadedIcon|null>} `null` when `url` is confirmed to
 *   have no icon to serve (cascade to the next candidate); otherwise a
 *   source to render.
 */
export async function loadIcon(url) {
  const cached = await readIconValue(url);
  if (cached) {
    return { src: URL.createObjectURL(cached), isObjectUrl: true };
  }

  let response;
  try {
    response = await fetch(url, { mode: "cors", credentials: "omit" });
  } catch {
    // Network error or a CORS-readability block — can't tell which from
    // here, and either way there's nothing to cache. Fall back to letting
    // the browser load the URL directly, same as before this cache existed.
    return { src: url, isObjectUrl: false };
  }

  if (!response.ok) {
    // A real "no icon" response (e.g. Brandfetch 401/404) — let the caller
    // move on to the next candidate rather than rendering a broken image.
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.startsWith("image/")) {
    return null;
  }

  const blob = await response.blob();
  writeIconValue(url, blob);
  return { src: URL.createObjectURL(blob), isObjectUrl: true };
}
