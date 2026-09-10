import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CONSENT_CHANGED_EVENT,
  getCookieConsent,
  hasAnalyticsConsent,
  setCookieConsent,
} from "./cookieConsent.js";

afterEach(() => {
  localStorage.clear();
});

describe("cookieConsent", () => {
  it("has no consent recorded until one is set", () => {
    expect(getCookieConsent()).toBeNull();
    expect(hasAnalyticsConsent()).toBe(false);
  });

  it("records and reads back an accepted analytics choice", () => {
    setCookieConsent({ analytics: true });

    expect(getCookieConsent()).toEqual({ analytics: true });
    expect(hasAnalyticsConsent()).toBe(true);
  });

  it("records and reads back a rejected analytics choice", () => {
    setCookieConsent({ analytics: false });

    expect(getCookieConsent()).toEqual({ analytics: false });
    expect(hasAnalyticsConsent()).toBe(false);
  });

  it("ignores malformed stored data rather than throwing", () => {
    localStorage.setItem("ec-cookie-consent", "{not json");

    expect(getCookieConsent()).toBeNull();
  });

  it("broadcasts a consent-changed event whenever the choice is set", () => {
    const handler = vi.fn();
    window.addEventListener(CONSENT_CHANGED_EVENT, handler);

    setCookieConsent({ analytics: true });

    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(CONSENT_CHANGED_EVENT, handler);
  });
});
