import { CONSENT_CHANGED_EVENT, hasAnalyticsConsent } from "./cookieConsent.js";

/**
 * Deliberately the *same* value for dev and prod, mirroring auth0Config.js's
 * own reasoning — see .env.example. GA simply never loads at all if this is
 * left unset (e.g. in the test environment, or before a GA4 property exists).
 */
export const gaMeasurementId = import.meta.env.VITE_GA_MEASUREMENT_ID;

export const isGaConfigured = Boolean(gaMeasurementId);

let scriptLoaded = false;
let listenerAttached = false;

function ensureScriptLoaded() {
  if (scriptLoaded) return;
  scriptLoaded = true;

  window.dataLayer = window.dataLayer || [];
  // gtag.js's own documented shim
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };
  window.gtag("js", new Date());
  // send_page_view is off — trackPageview() below fires pageviews itself
  // on every SPA route change instead of relying on GA's own load-time one.
  window.gtag("config", gaMeasurementId, { send_page_view: false });

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`;
  document.head.appendChild(script);
}

/**
 * GA's own documented live opt-out flag — the loaded gtag.js runtime checks
 * it before sending anything, so toggling it stops/resumes tracking
 * immediately within the same session without touching the injected
 * <script> tag. See https://developers.google.com/analytics/devguides/collection/gtagjs/user-opt-out
 */
function syncWithConsent() {
  if (hasAnalyticsConsent()) {
    window[`ga-disable-${gaMeasurementId}`] = false;
    ensureScriptLoaded();
  } else {
    window[`ga-disable-${gaMeasurementId}`] = true;
  }
}

/** Call once at app startup (see App.jsx). No-ops entirely if GA isn't
 * configured. Reacts live to consent changes via cookieConsent.js's
 * CONSENT_CHANGED_EVENT — no reload needed when the visitor flips the
 * Analytics switch in the cookie preferences panel. */
export function initAnalytics() {
  if (!isGaConfigured) return;

  syncWithConsent();

  if (!listenerAttached) {
    listenerAttached = true;
    window.addEventListener(CONSENT_CHANGED_EVENT, syncWithConsent);
  }
}

function canTrack() {
  return isGaConfigured && hasAnalyticsConsent() && typeof window.gtag === "function";
}

/** Fire on every client-side route change — GA4's own automatic pageview
 * is disabled above since it assumes full page loads, which an SPA never
 * does after the first one. */
export function trackPageview(path) {
  if (!canTrack()) return;
  window.gtag("event", "page_view", { page_path: path });
}

export function trackEvent(name, params = {}) {
  if (!canTrack()) return;
  window.gtag("event", name, params);
}
