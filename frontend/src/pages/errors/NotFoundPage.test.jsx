import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import NotFoundPage from "./NotFoundPage.jsx";

describe("NotFoundPage", () => {
  it("renders a plain-language heading and a way back to the dashboard", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to dashboard" })).toBeInTheDocument();
  });

  it("navigates to /dashboard when the action is clicked", () => {
    render(
      <MemoryRouter initialEntries={["/nope"]}>
        <Routes>
          <Route path="/dashboard" element={<p>Dashboard content</p>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Back to dashboard" }));

    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });
});
