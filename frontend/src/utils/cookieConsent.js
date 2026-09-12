const STORAGE_KEY = "ec-cookie-consent";

/** Broadcast whenever the visitor's consent choice changes, so anything
 * already running in this tab (e.g. analytics.js) can react live instead
 * of waiting for the next page load. Payload-less, same as CookieBanner's
 * own `ec:open-cookie-preferences` — listeners re-read the new value via
 * getCookieConsent()/hasAnalyticsConsent() rather than a `detail`. */
export const CONSENT_CHANGED_EVENT = "ec:consent-changed";

/**
 * The only real choice the cookie banner/preferences panel offers today —
 * see CookieBanner.jsx's own `CATEGORIES` and CookiePolicyPage.jsx for the
 * full breakdown. "Strictly necessary" (Auth0's own sign-in session) and
 * "Functional" (theme/hide-balances preference, plus the app's session/
 * local/IndexedDB performance caches) are always on — equiCast can't run
 * without the first, and none of the second involves any cross-site
 * tracking, so there's nothing to meaningfully opt out of there. Analytics
 * is the one category equiCast doesn't use *today* but might in future, so
 * it's the one real on/off switch, off by default and off whenever
 * "Reject non-essential" is chosen.
 */
const DEFAULT_CONSENT = { analytics: false };

function readStoredConsent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.analytics === "boolean" ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * `null` until the visitor has made a real choice (Accept all / Reject
 * non-essential / Save preferences) — CookieBanner shows itself only
 * while this is `null`, and stays hidden once it isn't, until localStorage
 * is cleared.
 */
export function getCookieConsent() {
  return readStoredConsent();
}

/** Records the visitor's choice — merged onto `DEFAULT_CONSENT` so a
 * caller only ever needs to pass the categories it actually knows about. */
export function setCookieConsent(consent) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...DEFAULT_CONSENT, ...consent }));
  } catch {
    // Storage can be unavailable (private browsing, disabled cookies) — the
    // choice just won't persist past this page load; CookieBanner will
    // simply ask again next time.
  }
  window.dispatchEvent(new Event(CONSENT_CHANGED_EVENT));
}

/** Whether analytics-category storage is currently allowed — this is what
 * analytics.js checks before loading/running Google Analytics. */
export function hasAnalyticsConsent() {
  return getCookieConsent()?.analytics === true;
}
