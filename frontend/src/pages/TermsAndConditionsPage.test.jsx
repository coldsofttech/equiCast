import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../api/identity.js";
import TermsAndConditionsPage from "./TermsAndConditionsPage.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../api/identity.js", () => ({ getMe: vi.fn() }));

// jsdom has no IntersectionObserver — AppShell's stickyTitle needs one.
beforeEach(() => {
  vi.mocked(getMe).mockResolvedValue({ default_currency: "USD" });
  global.IntersectionObserver = class {
    observe() {}
    disconnect() {}
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TermsAndConditionsPage", () => {
  describe("signed out", () => {
    beforeEach(() => {
      vi.mocked(useAuth0).mockReturnValue({ isAuthenticated: false });
    });

    it("renders the terms' real sections", () => {
      render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("heading", { name: "Terms and Conditions" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "What equiCast is" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Not financial advice" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Your account and data" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Acceptable use" })).toBeInTheDocument();
    });

    it("links to the LICENSE file and GitHub repository", () => {
      render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("link", { name: "the LICENSE file" })).toHaveAttribute(
        "href",
        "https://github.com/coldsofttech/equiCast/blob/main/LICENSE"
      );
      const repoLinks = screen.getAllByRole("link", { name: "equiCast's GitHub repository" });
      expect(
        repoLinks.some((link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast")
      ).toBe(true);
      expect(
        repoLinks.some(
          (link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast/issues"
        )
      ).toBe(true);
    });

    it("has no Topbar chrome", () => {
      render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      expect(screen.queryByLabelText("Search tickers")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Account")).not.toBeInTheDocument();
    });
  });

  describe("signed in", () => {
    beforeEach(() => {
      vi.mocked(useAuth0).mockReturnValue({
        isAuthenticated: true,
        user: { name: "Jane Doe", email: "jane@example.com" },
        getAccessTokenSilently: vi.fn(),
        logout: vi.fn(),
      });
    });

    it("still renders the terms content", () => {
      render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("heading", { name: "Terms and Conditions" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Acceptable use" })).toBeInTheDocument();
    });

    it("keeps the normal Topbar (search, currency, hide balances, account menu)", async () => {
      render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      expect(screen.getByLabelText("Search tickers")).toBeInTheDocument();
      expect(await screen.findByTitle("Default currency")).toHaveTextContent("USD");
      expect(screen.getByRole("button", { name: "Hide balances" })).toBeInTheDocument();
      expect(screen.getByLabelText("Account")).toBeInTheDocument();
    });

    it("renders a stickyTitle frozen-title bar, like AccountDetailPage/PieDetailPage", () => {
      const { container } = render(
        <MemoryRouter>
          <TermsAndConditionsPage />
        </MemoryRouter>
      );

      const frozenTitle = container.querySelector(".ec-frozen-title");
      expect(frozenTitle).not.toBeNull();
      expect(frozenTitle).toHaveTextContent("Terms and Conditions");
    });
  });
});
