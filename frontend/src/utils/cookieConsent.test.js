import { afterEach, describe, expect, it } from "vitest";
import { getCookieConsent, hasAnalyticsConsent, setCookieConsent } from "./cookieConsent.js";

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
});
