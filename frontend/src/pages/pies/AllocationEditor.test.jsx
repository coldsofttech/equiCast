import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { searchTickers } from "../../api/market.js";
import AllocationEditor from "./AllocationEditor.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({ searchTickers: vi.fn() }));

const HOLDINGS = [
  { id: "h-1", ticker: "AAPL", asset_class: "stock", allocation_pct: "60" },
  { id: "h-2", ticker: "VUSA", asset_class: "etf", allocation_pct: "40" },
];

/** Types `query` into the search field, presses Enter, and clicks the
 * first (only) mocked result to add it as a new row. */
async function searchAndAdd(query, result) {
  vi.mocked(searchTickers).mockResolvedValue({ results: [result] });
  fireEvent.change(screen.getByLabelText("Search ticker or name"), { target: { value: query } });
  fireEvent.keyDown(screen.getByLabelText("Search ticker or name"), { key: "Enter" });
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(result.ticker) }));
}

describe("AllocationEditor", () => {
  beforeEach(() => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the current total and disables save with no edits", () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} />);

    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("reallocates an existing holding and only sends what changed", () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={HOLDINGS} onSave={onSave} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "70" },
    });
    fireEvent.change(screen.getAllByLabelText("Allocation percent")[1], {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({
      add: [],
      remove: [],
      reallocate: [
        { id: "h-1", allocation_pct: "70" },
        { id: "h-2", allocation_pct: "30" },
      ],
    });
  });

  it("adds a new holding via ticker search", async () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={[HOLDINGS[0]]} onSave={onSave} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "50" },
    });
    await searchAndAdd("vwrl", { ticker: "VWRL", name: "Vanguard World", type: "etf" });
    fireEvent.change(screen.getAllByLabelText("Allocation percent")[1], {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({
      add: [{ ticker: "VWRL", asset_class: "etf", allocation_pct: "50" }],
      remove: [],
      reallocate: [{ id: "h-1", allocation_pct: "50" }],
    });
  });

  it("refuses to add a ticker that's already in the pie", async () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} />);

    await searchAndAdd("aapl", { ticker: "AAPL", name: "Apple", type: "stock" });

    expect(screen.getByRole("alert")).toHaveTextContent("AAPL is already in this pie.");
    expect(screen.getAllByLabelText("Allocation percent")).toHaveLength(2);
  });

  it("removes an existing holding", () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={[HOLDINGS[0]]} onSave={onSave} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(screen.queryByLabelText("Allocation percent")).not.toBeInTheDocument();
    expect(screen.getByText("No holdings yet — search below to add one.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({ add: [], remove: ["h-1"], reallocate: [] });
  });

  it("keeps save disabled while the total isn't 100%, and flags it as over once above", () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "70" },
    });

    expect(screen.getByText("110%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.getByRole("img", { name: "110% allocated, over 100%" })).toBeInTheDocument();
  });

  it("surfaces a save error passed in via props", () => {
    render(
      <AllocationEditor
        holdings={HOLDINGS}
        onSave={vi.fn()}
        error="Pie holdings must sum to exactly 100%."
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Pie holdings must sum to exactly 100%.");
  });
});
