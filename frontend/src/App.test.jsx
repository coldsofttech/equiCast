import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";

describe("App", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the equiCast heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "equiCast" })).toBeInTheDocument();
  });

  it("loads and displays ticker history on fetch", async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ticker: "AAPL", results: [{ date: "2024-01-01", close: 100 }] }),
    });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /fetch history/i }));

    await waitFor(() => expect(screen.getByText("1 rows loaded")).toBeInTheDocument());
  });

  it("shows an error message when the request fails", async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 500 });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /fetch history/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
