import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import OfflinePage from "./OfflinePage.jsx";

describe("OfflinePage", () => {
  it("renders a plain-language heading and no action button", () => {
    render(
      <MemoryRouter>
        <OfflinePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "You're offline" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
