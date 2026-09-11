import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ErrorBoundary from "./ErrorBoundary.jsx";

function Bomb() {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders children normally when nothing throws", () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <p>All good</p>
        </ErrorBoundary>
      </MemoryRouter>
    );

    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("renders AppErrorPage instead of crashing the tree when a child throws", () => {
    // React logs the caught error to the console by default (in addition
    // to componentDidCatch's own console.error) - silenced here so the
    // test output doesn't imply a real, unhandled failure.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();

    consoleError.mockRestore();
  });
});
