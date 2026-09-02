import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Drawer from "./Drawer.jsx";

describe("Drawer", () => {
  it("renders nothing when closed", () => {
    render(
      <Drawer open={false} onClose={vi.fn()} title="New account">
        content
      </Drawer>
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders its title and children when open", () => {
    render(
      <Drawer open onClose={vi.fn()} title="New account">
        <p>content</p>
      </Drawer>
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("New account")).toBeInTheDocument();
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="New account">
        content
      </Drawer>
    );

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on a backdrop click but not a panel click", () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="New account">
        <p>content</p>
      </Drawer>
    );

    fireEvent.click(screen.getByText("content"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("dialog").parentElement);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose from the close button", () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="New account">
        content
      </Drawer>
    );

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
