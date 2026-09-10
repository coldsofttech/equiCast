import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import TermsAndConditionsPage from "./TermsAndConditionsPage.jsx";

describe("TermsAndConditionsPage", () => {
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
    expect(repoLinks.some((link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast")).toBe(
      true
    );
    expect(
      repoLinks.some(
        (link) => link.getAttribute("href") === "https://github.com/coldsofttech/equiCast/issues"
      )
    ).toBe(true);
  });
});
