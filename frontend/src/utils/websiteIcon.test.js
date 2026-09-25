import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config/websiteIcons.json", () => ({
  default: {
    GOOGL: { website: "https://google.com" },
    NEE: { source: "/icons/NEE.svg" },
  },
}));

/** Fresh module instance per test, with VITE_BRANDFETCH_CLIENT_ID
 * re-stubbed before the module's top-level BRANDFETCH_CLIENT_ID const is
 * evaluated — same pattern as analytics.test.js's loadAnalytics. */
async function loadWebsiteIcon(clientId) {
  vi.stubEnv("VITE_BRANDFETCH_CLIENT_ID", clientId ?? "");
  vi.resetModules();
  return import("./websiteIcon.js");
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("websiteIconUrl", () => {
  it("builds a Google favicon URL from a website's domain", async () => {
    const { websiteIconUrl } = await loadWebsiteIcon();
    expect(websiteIconUrl("https://apple.com/investor", { size: 64 })).toBe(
      "https://www.google.com/s2/favicons?domain=apple.com&sz=64"
    );
  });

  it("returns null for a missing or unparseable website", async () => {
    const { websiteIconUrl } = await loadWebsiteIcon();
    expect(websiteIconUrl(null)).toBeNull();
    expect(websiteIconUrl("not a url")).toBeNull();
  });
});

describe("brandfetchIconUrl", () => {
  it("builds a ticker-based Brandfetch URL when a client id is configured", async () => {
    const { brandfetchIconUrl } = await loadWebsiteIcon("test-client-id");
    expect(brandfetchIconUrl("aapl")).toBe("https://cdn.brandfetch.io/ticker/AAPL?c=test-client-id");
  });

  it("returns null without a ticker", async () => {
    const { brandfetchIconUrl } = await loadWebsiteIcon("test-client-id");
    expect(brandfetchIconUrl(null)).toBeNull();
  });

  it("returns null without a configured client id", async () => {
    const { brandfetchIconUrl } = await loadWebsiteIcon();
    expect(brandfetchIconUrl("AAPL")).toBeNull();
  });
});

describe("resolveIconCandidates", () => {
  it("orders candidates Brandfetch, then Google favicon, then a local SVG override", async () => {
    const { resolveIconCandidates } = await loadWebsiteIcon("test-client-id");
    expect(resolveIconCandidates("NEE", "https://nexteraenergy.com")).toEqual([
      "https://cdn.brandfetch.io/ticker/NEE?c=test-client-id",
      "https://www.google.com/s2/favicons?domain=nexteraenergy.com&sz=128",
      "/icons/NEE.svg",
    ]);
  });

  it("skips Brandfetch without a configured client id", async () => {
    const { resolveIconCandidates } = await loadWebsiteIcon();
    expect(resolveIconCandidates("AAPL", "https://apple.com")).toEqual([
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);
  });

  it("substitutes an override's website for the Google-favicon fallback only", async () => {
    const { resolveIconCandidates } = await loadWebsiteIcon("test-client-id");
    // GOOGL's own profile website (a shared Alphabet domain) is overridden
    // for the favicon lookup, but Brandfetch is still looked up by ticker.
    expect(resolveIconCandidates("GOOGL", "https://abc.xyz")).toEqual([
      "https://cdn.brandfetch.io/ticker/GOOGL?c=test-client-id",
      "https://www.google.com/s2/favicons?domain=google.com&sz=128",
    ]);
  });

  it("returns an empty list with nothing to derive an icon from", async () => {
    const { resolveIconCandidates } = await loadWebsiteIcon("test-client-id");
    expect(resolveIconCandidates(null, null)).toEqual([]);
  });
});
