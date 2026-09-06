import { describe, expect, it } from "vitest";
import { profileCacheKey, readCachedProfile, writeCachedProfile } from "./profileCache.js";

describe("profileCache", () => {
  it("builds a profile key from asset class and symbol", () => {
    expect(profileCacheKey("stock", "aapl")).toBe("stock:AAPL:profile");
  });

  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedProfile("stock:AAPL:profile")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(
      writeCachedProfile("stock:AAPL:profile", { ticker: "AAPL" })
    ).resolves.toBeUndefined();
  });
});
