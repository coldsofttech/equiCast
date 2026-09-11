import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AppErrorPage from "./AppErrorPage.jsx";

describe("AppErrorPage", () => {
  it("renders a plain-language heading and a reload action", () => {
    render(
      <MemoryRouter>
        <AppErrorPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
  });

  it("reloads the page when the action is clicked", () => {
    const reload = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, reload },
    });

    render(
      <MemoryRouter>
        <AppErrorPage />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: "Reload page" }));

    expect(reload).toHaveBeenCalledTimes(1);

    Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
  });
});
