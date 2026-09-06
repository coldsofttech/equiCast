import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { searchTickers } from "../../api/market.js";
import HoldingComparePicker from "./HoldingComparePicker.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({ searchTickers: vi.fn() }));

function renderPicker(props = {}) {
  vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
  return render(
    <HoldingComparePicker
      currentTicker="AVGO"
      compareId=""
      compareLabel={null}
      onSelect={vi.fn()}
      onClear={vi.fn()}
      {...props}
    />
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("HoldingComparePicker", () => {
  it("does not search on every keystroke, only on Enter", () => {
    vi.mocked(searchTickers).mockResolvedValue({ results: [] });
    renderPicker();

    fireEvent.change(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), {
      target: { value: "aapl" },
    });
    expect(searchTickers).not.toHaveBeenCalled();

    fireEvent.keyDown(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), { key: "Enter" });
    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "aapl", { assetClass: "stock", pageSize: 8 });
    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "aapl", { assetClass: "etf", pageSize: 8 });
    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "aapl", {
      assetClass: "benchmark",
      pageSize: 8,
    });
  });

  it("merges stock/ETF/benchmark matches, excluding the current ticker, and selecting one calls onSelect", async () => {
    vi.mocked(searchTickers).mockImplementation((_api, _q, { assetClass }) => {
      if (assetClass === "stock") {
        return Promise.resolve({
          results: [
            { ticker: "AAPL", name: "Apple Inc.", type: "stock" },
            { ticker: "AVGO", name: "Broadcom Inc.", type: "stock" },
          ],
        });
      }
      if (assetClass === "etf") {
        return Promise.resolve({ results: [{ ticker: "VOO", name: "Vanguard S&P 500 ETF", type: "etf" }] });
      }
      return Promise.resolve({ results: [{ ticker: "NASDAQ100", name: "Nasdaq 100", type: "benchmark" }] });
    });
    const onSelect = vi.fn();
    renderPicker({ onSelect });

    fireEvent.focus(screen.getByLabelText("Compare against a stock, ETF, or benchmark"));
    fireEvent.change(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), { target: { value: "a" } });
    fireEvent.keyDown(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), { key: "Enter" });

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("VOO")).toBeInTheDocument();
    expect(screen.getByText("Nasdaq 100")).toBeInTheDocument();
    expect(screen.queryByText("Broadcom Inc.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("AAPL"));

    expect(onSelect).toHaveBeenCalledWith({
      compareId: "holding:AAPL",
      label: "Apple Inc.",
      ticker: "AAPL",
      assetClass: "stock",
    });
  });

  it("lets picking a quick-pick benchmark without searching, using its real key", () => {
    const onSelect = vi.fn();
    renderPicker({ onSelect });

    fireEvent.focus(screen.getByLabelText("Compare against a stock, ETF, or benchmark"));
    fireEvent.click(screen.getByRole("button", { name: "S&P 500" }));

    expect(onSelect).toHaveBeenCalledWith({
      compareId: "benchmark:SP500",
      label: "S&P 500",
      ticker: "SP500",
      assetClass: "benchmark",
    });
    expect(searchTickers).not.toHaveBeenCalled();
  });

  it("shows a chip with the active comparison and clears it", () => {
    const onClear = vi.fn();
    renderPicker({ compareId: "holding:AAPL", compareLabel: "Apple Inc.", onClear });

    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Compare against a stock, ETF, or benchmark")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Clear comparison"));
    expect(onClear).toHaveBeenCalled();
  });
});
