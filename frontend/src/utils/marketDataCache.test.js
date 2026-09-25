import { describe, expect, it } from "vitest";
import { clearAllCaches, readIconValue, writeIconValue } from "./marketDataCache.js";

describe("marketDataCache icons store", () => {
  // This test environment has no IndexedDB (see this module's own
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readIconValue("https://cdn.brandfetch.io/ticker/AAPL?c=id")).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    const blob = new Blob(["icon"], { type: "image/png" });
    await expect(writeIconValue("https://cdn.brandfetch.io/ticker/AAPL?c=id", blob)).resolves.toBeUndefined();
  });

  it("degrades to a no-op clear when IndexedDB is unavailable", async () => {
    await expect(clearAllCaches()).resolves.toBeUndefined();
  });
});
