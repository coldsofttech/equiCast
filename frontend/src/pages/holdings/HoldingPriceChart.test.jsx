import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { getEvents, getMetrics, getPrices, searchTickers } from "../../api/market.js";
import HoldingPriceChart from "./HoldingPriceChart.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({
  getEvents: vi.fn(),
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

  it("fetches events only once the Key events toggle is switched on", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });
    vi.mocked(getEvents).mockResolvedValue({ ticker: "AAPL", last_updated: null, events: [] });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);

    expect(getEvents).not.toHaveBeenCalled();

    // Key events lives on the OHLC readout row, which only renders once
    // price data has loaded — wait for it before interacting.
    await screen.findByLabelText("Key events");

    // Key events is disabled on the default "max" range (see
    // EVENTS_DISABLED_RANGES) — switch to an allowed one first.
    fireEvent.click(screen.getByRole("button", { name: "6M" }));
    fireEvent.click(screen.getByLabelText("Key events"));

    await waitFor(() =>
      expect(getEvents).toHaveBeenCalledWith(expect.any(Function), "stock", "AAPL")
    );
  });

  it("disables the Key events toggle on long ranges and turns it back off when switching to one", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });
    vi.mocked(getEvents).mockResolvedValue({ ticker: "AAPL", last_updated: null, events: [] });

    render(<HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />);

    // Default range is "max" — disabled. The toggle lives on the OHLC
    // readout row, which only renders once price data has loaded.
    expect(await screen.findByLabelText("Key events")).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "6M" }));
    expect(screen.getByLabelText("Key events")).toBeEnabled();

    fireEvent.click(screen.getByLabelText("Key events"));
    await waitFor(() => expect(getEvents).toHaveBeenCalled());
    expect(screen.getByLabelText("Key events")).toBeChecked();

    // Switching to a disabled range (2Y) turns events back off rather than
    // leaving the now-inaccessible toggle stuck checked.
    fireEvent.click(screen.getByRole("button", { name: "2Y" }));
    expect(screen.getByLabelText("Key events")).toBeDisabled();
    expect(screen.getByLabelText("Key events")).not.toBeChecked();
  });

  it("plots a marker for an in-range event and shows its details on hover", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });
    vi.mocked(getEvents).mockResolvedValue({
      ticker: "AAPL",
      last_updated: "2024-01-02T00:00:00Z",
      events: [
        {
          ticker: "AAPL",
          event_type: "earnings",
          date: "2024-01-02",
          eps_estimate: 1.5,
          reported_eps: 1.6,
          surprise_pct: 6.67,
          firm: null,
          from_grade: null,
          to_grade: null,
          action: null,
          price_target_action: null,
          current_price_target: null,
          prior_price_target: null,
          ratio: null,
          last_updated: "2024-01-02T00:00:00Z",
          source: "yfinance",
        },
      ],
    });

    const { container } = render(
      <HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />
    );
    // Key events lives on the OHLC readout row, which only renders once
    // price data has loaded — wait for it before interacting.
    await screen.findByLabelText("Key events");
    fireEvent.click(screen.getByRole("button", { name: "6M" }));
    fireEvent.click(screen.getByLabelText("Key events"));

    const dot = await waitFor(() => {
      const el = container.querySelector(".ec-pchart-event-dot--earnings");
      expect(el).not.toBeNull();
      return el;
    });

    fireEvent.mouseEnter(dot);

    expect(await screen.findByText("Earnings")).toBeInTheDocument();
    expect(screen.getByText("6.67%")).toBeInTheDocument();
  });

  it("merges same-day same-type events into one dot with a details modal", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });
    const ratingEvent = (firm, toGrade) => ({
      ticker: "AAPL",
      event_type: "rating",
      date: "2024-01-02",
      eps_estimate: null,
      reported_eps: null,
      surprise_pct: null,
      firm,
      from_grade: null,
      to_grade: toGrade,
      action: "main",
      price_target_action: null,
      current_price_target: null,
      prior_price_target: null,
      ratio: null,
      last_updated: "2024-01-02T00:00:00Z",
      source: "yfinance",
    });
    vi.mocked(getEvents).mockResolvedValue({
      ticker: "AAPL",
      last_updated: "2024-01-02T00:00:00Z",
      events: [ratingEvent("Morgan Stanley", "Overweight"), ratingEvent("Barclays", "Equal-Weight")],
    });

    const { container } = render(
      <HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />
    );
    // Key events lives on the OHLC readout row, which only renders once
    // price data has loaded — wait for it before interacting.
    await screen.findByLabelText("Key events");
    fireEvent.click(screen.getByRole("button", { name: "6M" }));
    fireEvent.click(screen.getByLabelText("Key events"));

    const dots = await waitFor(() => {
      const els = container.querySelectorAll(".ec-pchart-event-dot--rating");
      expect(els.length).toBe(1);
      return els;
    });

    fireEvent.mouseEnter(dots[0]);
    const detailsButton = await screen.findByRole("button", { name: "Click for details" });
    expect(screen.getByText("2")).toBeInTheDocument();

    // Regression: the cursor leaves the tiny dot before it ever reaches the
    // tooltip's own button — the tooltip must survive that gap (a short
    // close delay bridges it) rather than unmounting before the click.
    fireEvent.mouseLeave(dots[0]);
    fireEvent.click(detailsButton);

    // One table row per grouped event, one column per rating field.
    const table = await screen.findByRole("table");
    expect(screen.getByRole("columnheader", { name: "Analyst" })).toBeInTheDocument();
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + 2 events
    expect(within(rows[1]).getByText("Morgan Stanley")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Barclays")).toBeInTheDocument();
  });

  it("drops an event dated outside the chart's visible range", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    mockPrices({ AAPL: MAIN_BARS });
    vi.mocked(getEvents).mockResolvedValue({
      ticker: "AAPL",
      last_updated: "2020-01-01T00:00:00Z",
      events: [
        {
          ticker: "AAPL",
          event_type: "split",
          date: "2020-01-01", // well before MAIN_BARS' own earliest date
          eps_estimate: null,
          reported_eps: null,
          surprise_pct: null,
          firm: null,
          from_grade: null,
          to_grade: null,
          action: null,
          price_target_action: null,
          current_price_target: null,
          prior_price_target: null,
          ratio: 4.0,
          last_updated: "2020-01-01T00:00:00Z",
          source: "yfinance",
        },
      ],
    });

    const { container } = render(
      <HoldingPriceChart assetClass="stock" ticker="AAPL" currency="USD" />
    );
    // Key events lives on the OHLC readout row, which only renders once
    // price data has loaded — wait for it before interacting.
    await screen.findByLabelText("Key events");
    fireEvent.click(screen.getByRole("button", { name: "6M" }));
    fireEvent.click(screen.getByLabelText("Key events"));

    await waitFor(() => expect(getEvents).toHaveBeenCalled());
    expect(container.querySelector(".ec-pchart-event-dot--split")).toBeNull();
  });
});
