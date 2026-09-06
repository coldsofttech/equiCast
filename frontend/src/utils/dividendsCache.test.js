import { describe, expect, it } from "vitest";
import { dividendsCacheKey, readCachedDividends, writeCachedDividends } from "./dividendsCache.js";

describe("dividendsCache", () => {
  it("builds a dividends key from asset class and symbol", () => {
    expect(dividendsCacheKey("stock", "aapl")).toBe("stock:AAPL:dividends");
  });

  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedDividends("stock:AAPL:dividends")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedDividends("stock:AAPL:dividends", { ticker: "AAPL", dividends: [] })
    ).resolves.toBeUndefined();
  });
});
