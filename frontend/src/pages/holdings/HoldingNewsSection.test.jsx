import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import HoldingNewsSection from "./HoldingNewsSection.jsx";

function makeArticle(id) {
  return {
    id,
    title: `Headline ${id}`,
    url: `https://example.com/${id}`,
    publisher: "Example Wire",
    published_at: "2026-09-10T00:00:00Z",
    thumbnail_url: null,
  };
}

function newsWith(count) {
  return { news: Array.from({ length: count }, (_, i) => makeArticle(i + 1)) };
}

/** Stubs global ResizeObserver with one that immediately reports `width`
 * for whatever element it observes, mimicking a real layout measurement at
 * that container width — jsdom itself has no ResizeObserver (see the
 * `typeof ResizeObserver === "undefined"` guard in HoldingNewsSection.jsx),
 * so without this the component always falls back to DEFAULT_GRID_WIDTH. */
function stubResizeObserverWidth(width) {
  const original = globalThis.ResizeObserver;
  class FakeResizeObserver {
    constructor(callback) {
      this.callback = callback;
    }
    observe() {
      this.callback([{ contentRect: { width } }]);
    }
    disconnect() {}
  }
  globalThis.ResizeObserver = FakeResizeObserver;
  return () => {
    globalThis.ResizeObserver = original;
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HoldingNewsSection", () => {
  it("renders nothing when news is null", () => {
    const { container } = render(<HoldingNewsSection news={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when news carries no articles", () => {
    const { container } = render(<HoldingNewsSection news={{ news: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows up to 4 cards and 'See all' before any real width measurement (jsdom has no ResizeObserver)", () => {
    render(<HoldingNewsSection news={newsWith(6)} />);

    expect(screen.getAllByText(/^Headline \d$/)).toHaveLength(4);
    expect(screen.getByRole("button", { name: "See all" })).toBeInTheDocument();
  });

  it("shows every article with no 'See all' when they already fit in one row", () => {
    render(<HoldingNewsSection news={newsWith(3)} />);

    expect(screen.getAllByText(/^Headline \d$/)).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "See all" })).not.toBeInTheDocument();
  });

  it("shows fewer cards on a narrow panel, matching how many actually fit in one row", () => {
    const restore = stubResizeObserverWidth(400); // fits 1 card: floor((400+16)/236) = 1
    try {
      render(<HoldingNewsSection news={newsWith(3)} />);

      expect(screen.getAllByText(/^Headline \d$/)).toHaveLength(1);
      expect(screen.getByRole("button", { name: "See all" })).toBeInTheDocument();
    } finally {
      restore();
    }
  });

  it("shows more cards on a wide panel, still with no 'See all' once they all fit", () => {
    const restore = stubResizeObserverWidth(1600); // fits 6 cards: floor((1600+16)/236) = 6
    try {
      render(<HoldingNewsSection news={newsWith(5)} />);

      expect(screen.getAllByText(/^Headline \d$/)).toHaveLength(5);
      expect(screen.queryByRole("button", { name: "See all" })).not.toBeInTheDocument();
    } finally {
      restore();
    }
  });

  it("lists every article, not just the visible ones, in the 'See all' drawer table", async () => {
    render(<HoldingNewsSection news={newsWith(6)} />);

    fireEvent.click(screen.getByRole("button", { name: "See all" }));

    const table = await screen.findByRole("table");
    expect(table.querySelectorAll("tbody tr")).toHaveLength(6);
  });
});
