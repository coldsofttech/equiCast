import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useApi } from "../../api/useApi.js";
import { createPie } from "../../api/pies.js";
import CreatePortfolioDrawer from "./CreatePortfolioDrawer.jsx";

vi.mock("../../api/useApi.js", () => ({ useApi: vi.fn() }));
vi.mock("../../api/pies.js", () => ({ createPie: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CreatePortfolioDrawer", () => {
  it("creates the pie from just name/description and closes", async () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    const created = { id: "p-1", name: "Growth", description: "Long-term", holdings: [] };
    vi.mocked(createPie).mockResolvedValue(created);
    const onCreated = vi.fn();
    const onClose = vi.fn();

    render(
      <CreatePortfolioDrawer open accountId="a-1" onClose={onClose} onCreated={onCreated} />
    );

    expect(screen.queryByLabelText(/holdings/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Growth" } });
    fireEvent.change(screen.getByLabelText("Description", { exact: false }), {
      target: { value: "Long-term" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(created));
    expect(createPie).toHaveBeenCalledWith(expect.any(Function), {
      name: "Growth",
      description: "Long-term",
      account_id: "a-1",
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("surfaces a create error and stays open", async () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    vi.mocked(createPie).mockRejectedValue(new Error("Portfolio limit reached."));
    const onCreated = vi.fn();
    const onClose = vi.fn();

    render(
      <CreatePortfolioDrawer open accountId="a-1" onClose={onClose} onCreated={onCreated} />
    );

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Growth" } });
    fireEvent.change(screen.getByLabelText("Description", { exact: false }), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Portfolio limit reached.");
    expect(onCreated).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByText("New portfolio")).toBeInTheDocument();
  });

  it("clears a prior error when reopened via onClose/cancel", () => {
    vi.mocked(useApi).mockReturnValue(vi.fn());
    const onClose = vi.fn();

    render(
      <CreatePortfolioDrawer open accountId="a-1" onClose={onClose} onCreated={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
