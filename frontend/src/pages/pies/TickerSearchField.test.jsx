import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { searchTickers } from "../../api/market.js";
import TickerSearchField from "./TickerSearchField.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({ searchTickers: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TickerSearchField", () => {
  it("does not search on every keystroke, only on Enter", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [] });

    render(<TickerSearchField onSelect={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Search ticker or name"), { target: { value: "aapl" } });

    expect(searchTickers).not.toHaveBeenCalled();

    fireEvent.keyDown(screen.getByLabelText("Search ticker or name"), { key: "Enter" });

    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "aapl");
  });

  it("also searches on clicking the Search button", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [] });

    render(<TickerSearchField onSelect={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Search ticker or name"), { target: { value: "vwrl" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "vwrl");
  });

  it("shows results and calls onSelect, then resets the field", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({
      results: [{ ticker: "AAPL", name: "Apple Inc.", type: "stock", current_price: 190.5 }],
    });
    const onSelect = vi.fn();

    render(<TickerSearchField onSelect={onSelect} />);
    fireEvent.change(screen.getByLabelText("Search ticker or name"), { target: { value: "apple" } });
    fireEvent.keyDown(screen.getByLabelText("Search ticker or name"), { key: "Enter" });

    fireEvent.click(await screen.findByRole("button", { name: /AAPL.*Apple Inc\./s }));

    expect(onSelect).toHaveBeenCalledWith({ ticker: "AAPL", asset_class: "stock" });
    expect(screen.getByLabelText("Search ticker or name")).toHaveValue("");
  });

  it("shows a no-matches message for an empty result set", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [] });

    render(<TickerSearchField onSelect={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Search ticker or name"), { target: { value: "zzz" } });
    fireEvent.keyDown(screen.getByLabelText("Search ticker or name"), { key: "Enter" });

    expect(await screen.findByText("No matches for “zzz”.")).toBeInTheDocument();
  });
});
