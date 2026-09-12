import { describe, expect, it } from "vitest";
import { newsCacheKey, readCachedNews, writeCachedNews } from "./newsCache.js";

describe("newsCache", () => {
  it("builds a news key from asset class and symbol", () => {
    expect(newsCacheKey("stock", "aapl")).toBe("stock:AAPL:news");
  });

  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedNews("stock:AAPL:news")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedNews("stock:AAPL:news", { ticker: "AAPL", last_updated: null, news: [] })
    ).resolves.toBeUndefined();
  });
});
