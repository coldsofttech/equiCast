import { describe, expect, it } from "vitest";
import { readCachedAccounts, writeCachedAccounts, clearCachedAccounts } from "./accountsCache.js";

describe("accountsCache", () => {
  // This test environment has no IndexedDB (see marketDataCache.js's
  // docstring) — every call here exercises the same catch-and-degrade path
  // a real browser without IndexedDB support (or one that throws for some
  // other reason) would hit, proving it never throws through to the caller.
  it("degrades to a cache miss when IndexedDB is unavailable", async () => {
    await expect(readCachedAccounts()).resolves.toBeNull();
  });

  it("degrades to a no-op write when IndexedDB is unavailable", async () => {
    await expect(writeCachedAccounts([{ id: "1" }])).resolves.toBeUndefined();
  });

  it("degrades to a no-op clear when IndexedDB is unavailable", async () => {
    await expect(clearCachedAccounts()).resolves.toBeUndefined();
  });
});
