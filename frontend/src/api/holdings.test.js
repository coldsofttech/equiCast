import { describe, expect, it, vi } from "vitest";
import { createHolding, deleteHolding } from "./holdings.js";

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
});
