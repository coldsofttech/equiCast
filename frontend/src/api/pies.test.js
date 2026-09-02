import { describe, expect, it, vi } from "vitest";
import { createPie, deletePie, getPie, listPies, syncPieHoldings, updatePie } from "./pies.js";

describe("pies api", () => {
  it("lists every pie when no account_id is given", async () => {
    const api = vi.fn().mockResolvedValue([]);

    await listPies(api);

    expect(api).toHaveBeenCalledWith("/pies/");
  });

  it("filters by account_id when given", async () => {
    const api = vi.fn().mockResolvedValue([]);

    await listPies(api, { accountId: "a-1" });

    expect(api).toHaveBeenCalledWith("/pies/?account_id=a-1");
  });

  it("gets one pie by id", async () => {
    const api = vi.fn().mockResolvedValue({ id: "p-1" });

    await getPie(api, "p-1");

    expect(api).toHaveBeenCalledWith("/pies/p-1/");
  });

  it("posts a new pie", async () => {
    const api = vi.fn().mockResolvedValue({ id: "p-1" });
    const data = { name: "Growth", description: "Growth slice", account_id: "a-1" };

    await createPie(api, data);

    expect(api).toHaveBeenCalledWith("/pies/", { method: "POST", body: data });
  });

  it("patches only name/description", async () => {
    const api = vi.fn().mockResolvedValue({ id: "p-1" });

    await updatePie(api, "p-1", { name: "Renamed" });

    expect(api).toHaveBeenCalledWith("/pies/p-1/", { method: "PATCH", body: { name: "Renamed" } });
  });

  it("deletes with ?force=true when requested", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deletePie(api, "p-1", { force: true });

    expect(api).toHaveBeenCalledWith("/pies/p-1/?force=true", { method: "DELETE" });
  });

  it("PUTs the add/remove/reallocate batch to the holdings endpoint", async () => {
    const api = vi.fn().mockResolvedValue({ id: "p-1", holdings: [] });
    const batch = {
      add: [{ ticker: "AAPL", asset_class: "stock", allocation_pct: "50" }],
      remove: ["h-1"],
      reallocate: [{ id: "h-2", allocation_pct: "50" }],
    };

    await syncPieHoldings(api, "p-1", batch);

    expect(api).toHaveBeenCalledWith("/pies/p-1/holdings/", { method: "PUT", body: batch });
  });
});
