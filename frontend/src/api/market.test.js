import { describe, expect, it, vi } from "vitest";
import { searchTickers } from "./market.js";

describe("market api", () => {
  it("searches tickers by query with a default page size", async () => {
    const api = vi.fn().mockResolvedValue({ count: 1, results: [{ ticker: "AAPL" }] });

    await searchTickers(api, "aap");

    expect(api).toHaveBeenCalledWith("/market/search/?q=aap&page_size=10");
  });

  it("honors a custom page size", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { pageSize: 5 });

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page_size=5");
  });
});
