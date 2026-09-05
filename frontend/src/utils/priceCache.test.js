import { describe, expect, it } from "vitest";
import { priceCacheKey, readCachedPrices, writeCachedPrices } from "./priceCache.js";

describe("priceCache", () => {
  it("builds a key from asset class, symbol, and range", () => {
    expect(priceCacheKey("stock", "aapl", "1y")).toBe("stock:AAPL:1y");
  });

  // This test environment has no IndexedDB (see the module docstring) —
  // every call here exercises the same catch-and-degrade path a real
  // browser without IndexedDB support (or one that throws for some other
  // reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedPrices("stock:AAPL:1y")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedPrices("stock:AAPL:1y", { ticker: "AAPL", prices: [] })
    ).resolves.toBeUndefined();
  });
});
