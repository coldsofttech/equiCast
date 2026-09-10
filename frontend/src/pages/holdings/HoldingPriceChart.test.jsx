import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { getMetrics, getPrices, searchTickers } from "../../api/market.js";
import HoldingPriceChart from "./HoldingPriceChart.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({
  getMetrics: vi.fn(),
  getPrices: vi.fn(),
  searchTickers: vi.fn(),
}));


const MAIN_BARS = [
  { date: "2024-01-01", open: 100, high: 101, low: 99, close: 100 },
  { date: "2024-01-02", open: 105, high: 112, low: 104, close: 110 },
];

const COMPARE_BARS = [
  { date: "2024-01-01", open: 50, high: 51, low: 49, close: 50 },
  { date: "2024-01-02", open: 52, high: 56, low: 51, close: 55 },
];

function mockPrices(byTicker) {
  vi.mocked(getPrices).mockImplementation((_api, _assetClass, symbol) =>
    Promise.resolve({ ticker: symbol, currency: "USD", prices: byTicker[symbol] ?? [] })
  );
}

async function selectCompareTicker(result) {
  vi.mocked(searchTickers).mockImplementation((_api, _q, { assetClass }) =>
    Promise.resolve({ results: assetClass === result.type ? [result] : [] })
  );
  fireEvent.focus(screen.getByLabelText("Compare against a stock, ETF, or benchmark"));
  fireEvent.change(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), {
    target: { value: result.ticker },
  });
  fireEvent.keyDown(screen.getByLabelText("Compare against a stock, ETF, or benchmark"), { key: "Enter" });
  fireEvent.click(await screen.findByText(result.ticker));
}

beforeEach(() => {
  // Selecting a benchmark comparison also mounts HoldingBenchmarkRating
  // (see HoldingPriceChart.jsx), which calls getMetrics — not under test in
  // this file (see HoldingBenchmarkRating.test.jsx for that), so it's given
  // an always-resolving default here purely to avoid an unhandled rejection.
  vi.mocked(getMetrics).mockResolvedValue({});
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("HoldingPriceChart", () => {
  it("fetches this ticker's real prices for the default range", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);

    expect(getPrices).toHaveBeenCalledWith(expect.any(Function), "stock", "AAPL", { range: "max" });
  });

  it("fetches and plots a selected comparison ticker's own real prices, rebased to this ticker's start", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS, AVGO: COMPARE_BARS });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);

    await selectCompareTicker({ ticker: "AVGO", name: "Broadcom Inc.", type: "stock" });

    expect(getPrices).toHaveBeenCalledWith(expect.any(Function), "stock", "AVGO", { range: "max" });

    // Both series go from their own start to +10% by the last bar, so once
    // rebased/date-aligned they should read the same % change even though
    // AVGO's raw closes (50/55) are on a completely different price scale
    // than AAPL's (100/110).
    expect(await screen.findByText("Broadcom Inc.")).toBeInTheDocument();
    const changes = screen.getAllByText("▲ 10.0%");
    expect(changes).toHaveLength(2);
  });

  it("shows a loading caption while the comparison ticker's prices are in flight", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    let resolveCompare;
    vi.mocked(getPrices).mockImplementation((_api, _assetClass, symbol) => {
      if (symbol === "AAPL") return Promise.resolve({ ticker: symbol, currency: "USD", prices: MAIN_BARS });
      return new Promise((resolve) => {
        resolveCompare = () => resolve({ ticker: symbol, currency: "USD", prices: COMPARE_BARS });
      });
    });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);
    await selectCompareTicker({ ticker: "AVGO", name: "Broadcom Inc.", type: "stock" });

    expect(await screen.findByText("Loading Broadcom Inc.’s price history…")).toBeInTheDocument();

    resolveCompare();
    await screen.findByText("Broadcom Inc.");
    expect(screen.getAllByText("▲ 10.0%")).toHaveLength(2);
  });

  it("fetches and plots a quick-pick benchmark's own real prices, rebased to this ticker's start", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS, SP500: COMPARE_BARS });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);

    fireEvent.focus(screen.getByLabelText("Compare against a stock, ETF, or benchmark"));
    fireEvent.click(await screen.findByRole("button", { name: "S&P 500" }));

    expect(getPrices).toHaveBeenCalledWith(expect.any(Function), "benchmark", "SP500", { range: "max" });

    expect(await screen.findByText("S&P 500")).toBeInTheDocument();
    const changes = screen.getAllByText("▲ 10.0%");
    expect(changes).toHaveLength(2);

    // Picking a real benchmark also mounts HoldingBenchmarkRating (not a
    // holding/ticker comparison — that never rates, see the "assetClass ===
    // 'benchmark'" gate in this component); its own scoring logic is
    // covered by HoldingBenchmarkRating.test.jsx, this just checks the wiring.
    expect(getMetrics).toHaveBeenCalledWith(expect.any(Function), "stock", "AAPL");
    expect(getMetrics).toHaveBeenCalledWith(expect.any(Function), "benchmark", "SP500");
  });

  it("doesn't replay the reveal animation on a same-ticker range switch (issue #137)", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });

    const { container } = render(
      <HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />
    );

    // The reveal group (`.ec-chart-reveal`) is only rendered for area/candle
    // chart types — switch to Area so there's a real DOM node whose
    // identity can be tracked across the range switch below.
    fireEvent.click(await screen.findByRole("button", { name: "Area" }));
    const revealBefore = await waitFor(() => {
      const el = container.querySelector(".ec-chart-reveal");
      expect(el).not.toBeNull();
      return el;
    });

    fireEvent.click(screen.getByRole("button", { name: "1Y" }));
    await waitFor(() =>
      expect(getPrices).toHaveBeenCalledWith(expect.any(Function), "stock", "AAPL", {
        range: "1y",
      })
    );

    // A same-ticker range switch must not bump `revision` (see
    // hasRevealedRef) — if it did, the `key={revision}` on this group
    // would force React to unmount/remount it, replaying the "start from
    // nothing" reveal on top of the is-refreshing dim/undim and producing
    // the blink issue #137 reported. Same node reference == no remount.
    expect(container.querySelector(".ec-chart-reveal")).toBe(revealBefore);
  });

  it("replays the reveal animation when the ticker itself changes", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS, MSFT: MAIN_BARS });

    const { container, rerender } = render(
      <HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />
    );
    fireEvent.click(await screen.findByRole("button", { name: "Area" }));
    const revealBefore = await waitFor(() => {
      const el = container.querySelector(".ec-chart-reveal");
      expect(el).not.toBeNull();
      return el;
    });

    rerender(<HoldingPriceChart assetClass="stock" ticker="MSFT" currency="USD" />);
    await waitFor(() =>
      expect(getPrices).toHaveBeenCalledWith(expect.any(Function), "stock", "MSFT", {
        range: "max",
      })
    );

    // A genuinely different ticker is a fresh chart — hasRevealedRef resets
    // (see the [assetClass, ticker] effect), so this *should* remount and
    // replay the reveal, unlike the same-ticker case above.
    const revealAfter = await waitFor(() => {
      const el = container.querySelector(".ec-chart-reveal");
      expect(el).not.toBeNull();
      return el;
    });
    expect(revealAfter).not.toBe(revealBefore);
  });
});
