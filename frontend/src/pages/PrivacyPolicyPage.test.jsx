import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PrivacyPolicyPage from "./PrivacyPolicyPage.jsx";

describe("PrivacyPolicyPage", () => {
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
    expect(links.some((link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast/issues")).toBe(
      true
    );
  });
});
