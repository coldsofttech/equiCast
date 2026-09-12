import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import useOnlineStatus from "./useOnlineStatus.js";

function Probe() {
  const isOnline = useOnlineStatus();
  return <p>{isOnline ? "online" : "offline"}</p>;
}

afterEach(() => {
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
});

describe("useOnlineStatus", () => {
  it("reflects navigator.onLine on first render", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });

    render(<Probe />);

    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("flips to offline when the browser fires the offline event", () => {
    render(<Probe />);
    expect(screen.getByText("online")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("flips back to online when the browser fires the online event", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    render(<Probe />);
    expect(screen.getByText("offline")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(screen.getByText("online")).toBeInTheDocument();
  });
});
