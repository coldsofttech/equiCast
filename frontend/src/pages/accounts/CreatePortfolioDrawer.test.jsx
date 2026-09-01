import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useApi } from "../../api/useApi.js";
import { createPie } from "../../api/pies.js";
import CreatePortfolioDrawer from "./CreatePortfolioDrawer.jsx";

vi.mock("../../api/useApi.js", () => ({ useApi: vi.fn() }));
vi.mock("../../api/pies.js", () => ({ createPie: vi.fn(), syncPieHoldings: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CreatePortfolioDrawer", () => {
  it("creates the pie, then shows the allocation editor for it", async () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    const created = { id: "p-1", name: "Growth", description: "Long-term", holdings: [] };
    vi.mocked(createPie).mockResolvedValue(created);
    const onCreated = vi.fn();

    render(
      <CreatePortfolioDrawer
        open
        accountId="a-1"
        onClose={vi.fn()}
        onCreated={onCreated}
        onHoldingsSaved={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Growth" } });
    fireEvent.change(screen.getByLabelText("Description", { exact: false }), { target: { value: "Long-term" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Add holdings to Growth")).toBeInTheDocument();
    expect(createPie).toHaveBeenCalledWith(expect.any(Function), {
      name: "Growth",
      description: "Long-term",
      account_id: "a-1",
    });
    expect(onCreated).toHaveBeenCalledWith(created);
    expect(screen.getByText("No holdings yet — search below to add one.")).toBeInTheDocument();
  });

  it("resets back to step 1 after closing", async () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    vi.mocked(createPie).mockResolvedValue({ id: "p-1", name: "Growth", holdings: [] });
    const onClose = vi.fn();

    render(
      <CreatePortfolioDrawer
        open
        accountId="a-1"
        onClose={onClose}
        onCreated={vi.fn()}
        onHoldingsSaved={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Growth" } });
    fireEvent.change(screen.getByLabelText("Description", { exact: false }), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Add holdings to Growth");

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByText("New portfolio")).toBeInTheDocument();
  });

  it("surfaces a create error without leaving step 1", async () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    vi.mocked(createPie).mockRejectedValue(new Error("Portfolio limit reached."));

    render(
      <CreatePortfolioDrawer
        open
        accountId="a-1"
        onClose={vi.fn()}
        onCreated={vi.fn()}
        onHoldingsSaved={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Growth" } });
    fireEvent.change(screen.getByLabelText("Description", { exact: false }), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Portfolio limit reached.");
    expect(screen.getByText("New portfolio")).toBeInTheDocument();
  });
});
