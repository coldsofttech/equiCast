/**
 * True for a page-load failure severe enough to show ServiceUnavailablePage
 * in place of the page's own content, instead of an inline Alert —
 * `status` is `null`/`undefined` for a failure with no HTTP response at
 * all (the request never reached the API — DNS, CORS, the API Gateway
 * itself down) or a genuine 5xx once it did. Deliberately excludes every
 * 4xx: a 404/403/429/etc. is a normal, page-specific condition with its
 * own existing handling (a 429 already shows its own Alert with a
 * retry-after countdown — see ApiError's own `retryAfterSeconds` — not
 * this page).
 *
 * @param {number | null | undefined} status
 */
function isServiceUnavailableError(status) {
  return status == null || status >= 500;
}

export default isServiceUnavailableError;
