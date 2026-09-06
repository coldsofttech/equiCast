import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { getMetrics } from "../../api/market.js";
import HoldingBenchmarkRating from "./HoldingBenchmarkRating.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({ getMetrics: vi.fn() }));

function renderRating(props = {}) {
  vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
  return render(
    <HoldingBenchmarkRating
      assetClass="stock"
      ticker="AVGO"
      benchmarkKey="SP500"
      benchmarkLabel="S&P 500"
      {...props}
    />
  );
}

function mockMetrics(byKey) {
  vi.mocked(getMetrics).mockImplementation((_api, _assetClass, symbol) => {
    const result = byKey[symbol];
    return result ? Promise.resolve(result) : Promise.reject(new Error("no data"));
  });
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("HoldingBenchmarkRating", () => {
  it("fetches both sides' metrics via the given asset classes", () => {
    mockMetrics({ AVGO: { cagr_1y: 0.1 }, SP500: { cagr_1y: 0.05 } });
    renderRating();

    expect(getMetrics).toHaveBeenCalledWith(expect.any(Function), "stock", "AVGO");
    expect(getMetrics).toHaveBeenCalledWith(expect.any(Function), "benchmark", "SP500");
  });

  it("shows a loading caption while metrics are in flight", () => {
    vi.mocked(getMetrics).mockReturnValue(new Promise(() => {}));
    renderRating();

    expect(screen.getByText("Rating AVGO against S&P 500…")).toBeInTheDocument();
  });

  it("scores the percentage of metrics the holding beats the benchmark on", async () => {
    mockMetrics({
      AVGO: { cagr_1y: 0.2, cagr_3y: 0.15, cagr_5y: 0.1, sharpe_ratio: 1.5 },
      SP500: { cagr_1y: 0.1, cagr_3y: 0.2, cagr_5y: 0.05, sharpe_ratio: 1.2 },
    });
    renderRating();

    // Beats on cagr_1y, cagr_5y, sharpe_ratio; trails on cagr_3y -> 3/4 = 75.
    expect(await screen.findByText("75/100 · Outperforming")).toBeInTheDocument();
    expect(
      screen.getByText("Beats the benchmark on 3 of 4 metrics S&P 500 and AVGO both have data for.")
    ).toBeInTheDocument();
  });

  it("excludes a metric missing on either side from the score", async () => {
    mockMetrics({
      AVGO: { cagr_1y: 0.2, cagr_3y: null, sharpe_ratio: 1.0 },
      SP500: { cagr_1y: 0.1, cagr_3y: 0.2, sharpe_ratio: 1.2 },
    });
    renderRating();

    // cagr_5y missing on both; cagr_3y missing on AVGO -> excluded. Rated:
    // cagr_1y (beats), sharpe_ratio (trails) -> 1/2 = 50.
    expect(await screen.findByText("50/100 · Tracking the benchmark")).toBeInTheDocument();
  });

  it("shows a not-enough-data message when nothing overlaps", async () => {
    mockMetrics({ AVGO: { cagr_1y: null }, SP500: { cagr_1y: null } });
    renderRating();

    expect(
      await screen.findByText("Not enough overlapping data to rate AVGO against S&P 500 yet.")
    ).toBeInTheDocument();
  });

  it("shows an error caption when a metrics fetch fails", async () => {
    vi.mocked(getMetrics).mockRejectedValue(new Error("boom"));
    renderRating();

    expect(await screen.findByText("Couldn’t load a rating against S&P 500.")).toBeInTheDocument();
  });
});
