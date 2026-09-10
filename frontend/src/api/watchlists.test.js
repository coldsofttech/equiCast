import { describe, expect, it, vi } from "vitest";
import {
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  updateWatchlist,
} from "./watchlists.js";

describe("watchlists api", () => {
  it("lists watchlists from /watchlists/", async () => {
    const api = vi.fn().mockResolvedValue([]);

    await listWatchlists(api);

    expect(api).toHaveBeenCalledWith("/watchlists/");
  });

  it("gets one watchlist by id", async () => {
    const api = vi.fn().mockResolvedValue({ id: "w-1" });

    await getWatchlist(api, "w-1");

    expect(api).toHaveBeenCalledWith("/watchlists/w-1/");
  });

  it("posts a new watchlist", async () => {
    const api = vi.fn().mockResolvedValue({ id: "w-1" });
    const data = { name: "Tech Watch", description: "Big tech names" };

    await createWatchlist(api, data);

    expect(api).toHaveBeenCalledWith("/watchlists/", { method: "POST", body: data });
  });

  it("patches only the given fields", async () => {
    const api = vi.fn().mockResolvedValue({ id: "w-1" });

    await updateWatchlist(api, "w-1", { name: "Renamed" });

    expect(api).toHaveBeenCalledWith("/watchlists/w-1/", {
      method: "PATCH",
      body: { name: "Renamed" },
    });
  });

  it("deletes without a force query param by default", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteWatchlist(api, "w-1");

    expect(api).toHaveBeenCalledWith("/watchlists/w-1/", { method: "DELETE" });
  });

  it("appends ?force=true when force is requested", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteWatchlist(api, "w-1", { force: true });

    expect(api).toHaveBeenCalledWith("/watchlists/w-1/?force=true", { method: "DELETE" });
  });
});
