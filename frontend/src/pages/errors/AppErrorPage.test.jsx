import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import AppErrorPage from "./AppErrorPage.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppErrorPage", () => {
  describe("signed in", () => {
    beforeEach(() => {
      vi.mocked(useAuth0).mockReturnValue({
        isAuthenticated: true,
        user: { name: "Jane Doe", email: "jane@example.com" },
        getAccessTokenSilently: vi.fn(),
        logout: vi.fn(),
      });
    });

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

    it("keeps the normal Topbar and footer, same as NotFoundPage/ServiceUnavailablePage", () => {
      render(
        <MemoryRouter>
          <AppErrorPage />
        </MemoryRouter>
      );

      expect(screen.getByLabelText("Search tickers")).toBeInTheDocument();
      expect(screen.getByLabelText("Account")).toBeInTheDocument();
      expect(screen.getByText(/equiCast/, { selector: ".ec-landing-foot-links span" })).toBeInTheDocument();
    });
  });

  describe("signed out", () => {
    beforeEach(() => {
      vi.mocked(useAuth0).mockReturnValue({
        isAuthenticated: false,
        user: undefined,
        getAccessTokenSilently: vi.fn(),
        logout: vi.fn(),
      });
    });

    it("renders a plain-language heading and a reload action", () => {
      render(
        <MemoryRouter>
          <AppErrorPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
    });

    it("shows the signed-out header instead of the search box and account menu (GitHub issue #213)", () => {
      render(
        <MemoryRouter>
          <AppErrorPage />
        </MemoryRouter>
      );

      expect(screen.getByLabelText("Go to equiCast")).toBeInTheDocument();
      expect(screen.queryByLabelText("Search tickers")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Account")).not.toBeInTheDocument();
      expect(screen.getByText(/equiCast/, { selector: ".ec-landing-foot-links span" })).toBeInTheDocument();
    });
  });
});
