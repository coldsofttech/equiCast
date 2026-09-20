import { describe, expect, it, vi } from "vitest";
import { apiFetch } from "./client.js";
import { getPublicDemoPrices } from "./publicMarket.js";

vi.mock("./client.js", () => ({ apiFetch: vi.fn() }));

describe("publicMarket api", () => {
  it("fetches the fixed demo-prices endpoint with no auth", async () => {
    const payload = { tickers: [{ ticker: "AAPL", asset_class: "stock", name: "Apple Inc." }] };
    vi.mocked(apiFetch).mockResolvedValue(payload);

    const result = await getPublicDemoPrices();

    expect(apiFetch).toHaveBeenCalledWith("/market/public/demo-prices/");
    expect(result).toEqual(payload);
  });
});
