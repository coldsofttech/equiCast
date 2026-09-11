import { describe, expect, it } from "vitest";
import { priceCacheKey, readCachedPrices, writeCachedPrices } from "./priceCache.js";

describe("priceCache", () => {
  it("builds a price key from asset class and symbol", () => {
    expect(priceCacheKey("stock", "aapl")).toBe("stock:AAPL:prices");
  });

  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedPrices("stock:AAPL:prices")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedPrices("stock:AAPL:prices", { ticker: "AAPL", daily: [], weekly: [], monthly: [] })
    ).resolves.toBeUndefined();
  });
});
