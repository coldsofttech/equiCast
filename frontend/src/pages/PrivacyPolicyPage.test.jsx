import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../api/identity.js";
import PrivacyPolicyPage from "./PrivacyPolicyPage.jsx";

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

describe("PrivacyPolicyPage", () => {
  describe("signed out", () => {
    beforeEach(() => {
      vi.mocked(useAuth0).mockReturnValue({ isAuthenticated: false });
    });

    it("renders the policy's real sections", () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Information we collect" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Where it's stored" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Who we share it with" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Deleting your data" })).toBeInTheDocument();
    });

    it("links to the GitHub repository for questions", () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      const links = screen.getAllByRole("link", { name: "equiCast's GitHub repository" });
      expect(
        links.some((link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast/issues")
      ).toBe(true);
    });

    it("has no Topbar chrome", () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      expect(screen.queryByLabelText("Search tickers")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Account")).not.toBeInTheDocument();
    });

    it("renders the shared PublicHeader (logo link + theme toggle)", () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("link", { name: "Go to equiCast" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("button", { name: /switch to (dark|light) theme/i })).toBeInTheDocument();
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

    it("still renders the policy content", () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Deleting your data" })).toBeInTheDocument();
    });

    it("keeps the normal Topbar (search, currency, hide balances, account menu)", async () => {
      render(
        <MemoryRouter>
          <PrivacyPolicyPage />
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
          <PrivacyPolicyPage />
        </MemoryRouter>
      );

      const frozenTitle = container.querySelector(".ec-frozen-title");
      expect(frozenTitle).not.toBeNull();
      expect(frozenTitle).toHaveTextContent("Privacy Policy");
    });
  });
});
