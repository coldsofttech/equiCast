import { describe, expect, it } from "vitest";
import { metricsCacheKey, readCachedMetrics, writeCachedMetrics } from "./metricsCache.js";

describe("metricsCache", () => {
  it("builds a metrics key from asset class and symbol", () => {
    expect(metricsCacheKey("stock", "aapl")).toBe("stock:AAPL:metrics");
  });

  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedMetrics("stock:AAPL:metrics")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedMetrics("stock:AAPL:metrics", { volatility: 0.23 })
    ).resolves.toBeUndefined();
  });
});
