import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getPublicDemoPrices } from "../api/publicMarket.js";
import DemoChart from "./DemoChart.jsx";

vi.mock("../api/publicMarket.js", () => ({ getPublicDemoPrices: vi.fn() }));

const TICKERS = [
  {
    ticker: "AAPL",
    asset_class: "stock",
    name: "Apple Inc.",
    currency: "USD",
    prices: [
      { date: "2026-01-02", open: 100, high: 101, low: 99, close: 100.5 },
      { date: "2026-01-03", open: 100.5, high: 103, low: 100, close: 102 },
    ],
  },
  {
    ticker: "NVDA",
    asset_class: "stock",
    name: "NVIDIA",
    currency: "USD",
    prices: [{ date: "2026-01-02", open: 50, high: 52, low: 49, close: 51 }],
  },
  {
    ticker: "VOO",
    asset_class: "etf",
    name: "Vanguard S&P 500 ETF",
    currency: "USD",
    prices: [{ date: "2026-01-02", open: 400, high: 405, low: 398, close: 402 }],
  },
];

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DemoChart", () => {
  it("shows a loading state, then renders tickers", async () => {
    vi.mocked(getPublicDemoPrices).mockResolvedValue({ tickers: TICKERS });

    render(<DemoChart />);

    expect(screen.getByText(/loading prices/i)).toBeInTheDocument();

    expect(await screen.findByRole("tab", { name: "AAPL" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "NVDA" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "VOO" })).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
  });

  it("switches ticker on tab click", async () => {
    vi.mocked(getPublicDemoPrices).mockResolvedValue({ tickers: TICKERS });

    render(<DemoChart />);
    await screen.findByRole("tab", { name: "AAPL" });

    fireEvent.click(screen.getByRole("tab", { name: "NVDA" }));

    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    vi.mocked(getPublicDemoPrices).mockRejectedValue(new Error("network down"));

    render(<DemoChart />);

    expect(await screen.findByText(/temporarily unavailable/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/loading prices/i)).not.toBeInTheDocument());
  });
});
