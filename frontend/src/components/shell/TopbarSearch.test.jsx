import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { searchTickers } from "../../api/market.js";
import TopbarSearch from "./TopbarSearch.jsx";

vi.mock("react-router-dom", () => ({ useNavigate: vi.fn() }));
vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/market.js", () => ({ searchTickers: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

function typeAndEnter(value) {
  fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value } });
  fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });
}

describe("TopbarSearch", () => {
  it("does not search on every keystroke, only on Enter", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [], count: 0 });

    render(<TopbarSearch />);
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "aapl" } });

    expect(searchTickers).not.toHaveBeenCalled();
  });

  it("opens a preview dropdown of results on Enter instead of navigating", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);
    vi.mocked(searchTickers).mockResolvedValue({
      results: [{ ticker: "AAPL", name: "Apple Inc.", type: "stock", current_price: 190.5 }],
      count: 1,
    });

    render(<TopbarSearch />);
    typeAndEnter("aapl");

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("shows a favicon-style icon for a result with a website, and none for one without", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(useNavigate).mockReturnValue(vi.fn());
    vi.mocked(searchTickers).mockResolvedValue({
      results: [
        {
          ticker: "AAPL",
          name: "Apple Inc.",
          type: "stock",
          current_price: 190.5,
          website: "https://www.apple.com",
        },
        { ticker: "GBPUSD", name: "British Pound to US Dollar", type: "fx", current_price: 1.27 },
      ],
      count: 2,
    });

    const { container } = render(<TopbarSearch />);
    typeAndEnter("a");

    await screen.findByText("AAPL");
    const icons = container.querySelectorAll(".ec-topbar-search-result img");
    expect(icons).toHaveLength(1);
    expect(icons[0].src).toContain("apple.com");
  });

  it("caps the preview at 7 results and shows a total count on More results", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(useNavigate).mockReturnValue(vi.fn());
    vi.mocked(searchTickers).mockResolvedValue({
      results: Array.from({ length: 7 }, (_, i) => ({
        ticker: `T${i}`,
        name: `Ticker ${i}`,
        type: "stock",
        current_price: 1,
      })),
      count: 42,
    });

    render(<TopbarSearch />);
    typeAndEnter("t");

    expect(searchTickers).toHaveBeenCalledWith(expect.any(Function), "t", { pageSize: 7 });
    expect(await screen.findByRole("button", { name: "More results (42)" })).toBeInTheDocument();
  });

  it("navigates to /search only when More results is clicked", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);
    vi.mocked(searchTickers).mockResolvedValue({
      results: [{ ticker: "AAPL", name: "Apple Inc.", type: "stock", current_price: 190.5 }],
      count: 1,
    });

    render(<TopbarSearch />);
    typeAndEnter("aapl");

    fireEvent.click(await screen.findByRole("button", { name: "More results" }));

    expect(navigate).toHaveBeenCalledWith("/search?q=aapl");
  });

  it("URL-encodes the query when navigating from More results", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);
    vi.mocked(searchTickers).mockResolvedValue({
      results: [{ ticker: "SPX", name: "S&P 500", type: "stock", current_price: 5000 }],
      count: 1,
    });

    render(<TopbarSearch />);
    typeAndEnter("S&P 500");

    fireEvent.click(await screen.findByRole("button", { name: "More results" }));

    expect(navigate).toHaveBeenCalledWith("/search?q=S%26P%20500");
  });

  it("shows a no-matches message for an empty result set", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [], count: 0 });

    render(<TopbarSearch />);
    typeAndEnter("zzz");

    expect(await screen.findByText("No matches for “zzz”.")).toBeInTheDocument();
  });

  it("does nothing on Enter with an empty/blank query", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [], count: 0 });

    render(<TopbarSearch />);
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "   " } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });

    expect(searchTickers).not.toHaveBeenCalled();
  });

  it("does not search on other keys", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(searchTickers).mockResolvedValue({ results: [], count: 0 });

    render(<TopbarSearch />);
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "aapl" } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "a" });

    expect(searchTickers).not.toHaveBeenCalled();
  });
});
