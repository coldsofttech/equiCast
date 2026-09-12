import { afterEach, describe, expect, it, vi } from "vitest";
import { setCookieConsent } from "./cookieConsent.js";

/** Fresh module instance per test (own scriptLoaded/listenerAttached
 * flags), with import.meta.env.VITE_GA_MEASUREMENT_ID re-stubbed before
 * the module's top-level `gaMeasurementId`/`isGaConfigured` const are
 * evaluated. A distinct GA id per test keeps any leftover window listener
 * from a previous test's module instance from touching this test's own
 * `ga-disable-*` flag. */
async function loadAnalytics(gaId) {
  vi.stubEnv("VITE_GA_MEASUREMENT_ID", gaId ?? "");
  vi.resetModules();
  return import("./analytics.js");
}

function resetGtagGlobals() {
  delete window.dataLayer;
  delete window.gtag;
  Object.keys(window)
    .filter((key) => key.startsWith("ga-disable-"))
    .forEach((key) => delete window[key]);
  document.querySelectorAll('script[src*="googletagmanager"]').forEach((el) => el.remove());
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllEnvs();
  resetGtagGlobals();
});

describe("analytics", () => {
  it("is not configured, and never loads or tracks, when the measurement id is unset", async () => {
    const { isGaConfigured, initAnalytics, trackEvent, trackPageview } = await loadAnalytics();

    expect(isGaConfigured).toBe(false);

    setCookieConsent({ analytics: true });
    initAnalytics();
    trackEvent("search");
    trackPageview("/dashboard");

    expect(window.gtag).toBeUndefined();
  });

  it("does not load the script or track without analytics consent", async () => {
    const gaId = "G-TEST-NOCONSENT";
    setCookieConsent({ analytics: false });
    const { initAnalytics, trackEvent, trackPageview } = await loadAnalytics(gaId);

    initAnalytics();
    expect(document.querySelector(`script[src*="${gaId}"]`)).toBeNull();

    trackEvent("search");
    trackPageview("/dashboard");
    expect(window.gtag).toBeUndefined();
  });

  it("loads the script and tracks pageviews/events once consent is granted", async () => {
    const gaId = "G-TEST-CONSENT";
    setCookieConsent({ analytics: true });
    const { initAnalytics, trackEvent, trackPageview } = await loadAnalytics(gaId);

    initAnalytics();

    expect(document.querySelector(`script[src*="${gaId}"]`)).not.toBeNull();
    expect(typeof window.gtag).toBe("function");
    expect(window[`ga-disable-${gaId}`]).toBe(false);

    trackEvent("search", { search_term: "aapl" });
    trackPageview("/dashboard");

    const eventNames = window.dataLayer.filter((entry) => entry[0] === "event").map((entry) => entry[1]);
    expect(eventNames).toEqual(expect.arrayContaining(["search", "page_view"]));
  });

  it("stops and resumes tracking live on a consent change, without re-injecting the script", async () => {
    const gaId = "G-TEST-LIVE";
    setCookieConsent({ analytics: true });
    const { initAnalytics, trackEvent } = await loadAnalytics(gaId);

    initAnalytics();
    expect(document.querySelectorAll(`script[src*="${gaId}"]`)).toHaveLength(1);

    setCookieConsent({ analytics: false });
    expect(window[`ga-disable-${gaId}`]).toBe(true);

    trackEvent("search");
    expect(
      window.dataLayer.filter((entry) => entry[0] === "event" && entry[1] === "search")
    ).toHaveLength(0);

    setCookieConsent({ analytics: true });
    expect(window[`ga-disable-${gaId}`]).toBe(false);
    expect(document.querySelectorAll(`script[src*="${gaId}"]`)).toHaveLength(1);

    trackEvent("search");
    expect(
      window.dataLayer.filter((entry) => entry[0] === "event" && entry[1] === "search")
    ).toHaveLength(1);
  });
});
