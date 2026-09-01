import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useNavigate } from "react-router-dom";
import TopbarSearch from "./TopbarSearch.jsx";

vi.mock("react-router-dom", () => ({ useNavigate: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TopbarSearch", () => {
  it("navigates to /search with the typed query on Enter", () => {
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);

    render(<TopbarSearch />);
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "aapl" } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });

    expect(navigate).toHaveBeenCalledWith("/search?q=aapl");
  });

  it("URL-encodes the query", () => {
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);

    render(<TopbarSearch />);
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "S&P 500" } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });

    expect(navigate).toHaveBeenCalledWith("/search?q=S%26P%20500");
  });

  it("does nothing on Enter with an empty/blank query", () => {
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);

    render(<TopbarSearch />);
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "   " } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "Enter" });

    expect(navigate).not.toHaveBeenCalled();
  });

  it("does not navigate on other keys", () => {
    const navigate = vi.fn();
    vi.mocked(useNavigate).mockReturnValue(navigate);

    render(<TopbarSearch />);
    fireEvent.change(screen.getByLabelText("Search tickers"), { target: { value: "aapl" } });
    fireEvent.keyDown(screen.getByLabelText("Search tickers"), { key: "a" });

    expect(navigate).not.toHaveBeenCalled();
  });
});
