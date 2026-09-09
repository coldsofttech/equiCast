import { describe, expect, it, vi } from "vitest";
import { getDividends, getEvents, getMetrics, getPrices, getProfile, searchTickers } from "./market.js";

describe("market api", () => {
  it("searches tickers by query with default page/page size", async () => {
    const api = vi.fn().mockResolvedValue({ count: 1, results: [{ ticker: "AAPL" }] });

    await searchTickers(api, "aap");

    expect(api).toHaveBeenCalledWith("/market/search/?q=aap&page=1&page_size=10");
  });

  it("honors a custom page size", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { pageSize: 5 });

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page=1&page_size=5");
  });

  it("honors a custom page", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { page: 3 });

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page=3&page_size=10");
  });

  it("includes asset_class when given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { assetClass: "etf" });

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page=1&page_size=10&asset_class=etf");
  });

  it("narrows the search to one asset class when given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "usdgbp", { assetClass: "fx" });

    expect(api).toHaveBeenCalledWith("/market/search/?q=usdgbp&page=1&page_size=10&asset_class=fx");
  });

  it("includes min/max market cap when given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { minMarketCap: 1_000_000_000, maxMarketCap: 200_000_000_000 });

    expect(api).toHaveBeenCalledWith(
      "/market/search/?q=vwrl&page=1&page_size=10&min_market_cap=1000000000&max_market_cap=200000000000"
    );
  });

  it("omits market cap params entirely when not given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl");

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page=1&page_size=10");
  });

  it("includes exchange/region when given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl", { exchange: "NMS", region: "us" });

    expect(api).toHaveBeenCalledWith(
      "/market/search/?q=vwrl&page=1&page_size=10&exchange=NMS&region=us"
    );
  });

  it("omits exchange/region entirely when not given", async () => {
    const api = vi.fn().mockResolvedValue({ count: 0, results: [] });

    await searchTickers(api, "vwrl");

    expect(api).toHaveBeenCalledWith("/market/search/?q=vwrl&page=1&page_size=10");
  });

  it("fetches a symbol's profile", async () => {
    const api = vi.fn().mockResolvedValue({ ticker: "AAPL", currency: "USD" });

    await getProfile(api, "stock", "AAPL");

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/profile/");
  });

  it("fetches a symbol's metrics", async () => {
    const api = vi.fn().mockResolvedValue({ volatility: 0.23, trailing_pe: 28.5 });

    await getMetrics(api, "stock", "AAPL");

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/metrics/");
  });

  it("fetches a symbol's dividends", async () => {
    const api = vi.fn().mockResolvedValue({ ticker: "AAPL", currency: "USD", dividends: [] });

    await getDividends(api, "stock", "AAPL");

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/dividends/");
  });

  it("fetches a symbol's events", async () => {
    const api = vi.fn().mockResolvedValue({ ticker: "AAPL", last_updated: null, events: [] });

    await getEvents(api, "stock", "AAPL");

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/events/");
  });

  it("defaults to the max range when none is given", async () => {
    const api = vi.fn().mockResolvedValue({ ticker: "AAPL", prices: [] });

    await getPrices(api, "stock", "AAPL");

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/prices/?range=max");
  });

  it("passes a given range through as a query param", async () => {
    const api = vi.fn().mockResolvedValue({ ticker: "AAPL", prices: [] });

    await getPrices(api, "stock", "AAPL", { range: "1y" });

    expect(api).toHaveBeenCalledWith("/market/stock/AAPL/prices/?range=1y");
  });
});
