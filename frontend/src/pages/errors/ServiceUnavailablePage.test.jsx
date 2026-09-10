import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ServiceUnavailablePage from "./ServiceUnavailablePage.jsx";

describe("ServiceUnavailablePage", () => {
  it("renders a plain-language heading and a retry action", () => {
    render(
      <MemoryRouter>
        <ServiceUnavailablePage />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "equiCast is temporarily unavailable" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("calls the caller's own onRetry instead of reloading when given one", () => {
    const onRetry = vi.fn();
    render(
      <MemoryRouter>
        <ServiceUnavailablePage onRetry={onRetry} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
