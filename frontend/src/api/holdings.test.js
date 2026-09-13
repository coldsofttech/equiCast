import { describe, expect, it, vi } from "vitest";
import { createHolding, deleteHolding, updateHoldingTaxOverride } from "./holdings.js";

describe("holdings api", () => {
  it("posts a new direct holding", async () => {
    const api = vi.fn().mockResolvedValue({ id: "h-1", ticker: "AAPL", asset_class: "stock" });
    const data = { ticker: "AAPL", asset_class: "stock", account_id: "a-1" };

    await createHolding(api, data);

    expect(api).toHaveBeenCalledWith("/holdings/", { method: "POST", body: data });
  });

  it("deletes a holding by id", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteHolding(api, "h-1");

    expect(api).toHaveBeenCalledWith("/holdings/h-1/", { method: "DELETE" });
  });

  it("patches tax_override_pct", async () => {
    const api = vi.fn().mockResolvedValue({ id: "h-1", tax_override_pct: 30 });

    await updateHoldingTaxOverride(api, "h-1", 30);

    expect(api).toHaveBeenCalledWith("/holdings/h-1/", {
      method: "PATCH",
      body: { tax_override_pct: 30 },
    });
  });

  it("patches tax_override_pct with null to clear it", async () => {
    const api = vi.fn().mockResolvedValue({ id: "h-1", tax_override_pct: null });

    await updateHoldingTaxOverride(api, "h-1", null);

    expect(api).toHaveBeenCalledWith("/holdings/h-1/", {
      method: "PATCH",
      body: { tax_override_pct: null },
    });
  });
});
