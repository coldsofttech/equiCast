import { fireEvent, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssetIcon from "./AssetIcon.jsx";
import { resolveIconCandidates } from "../../utils/websiteIcon.js";
import { loadIcon } from "../../utils/iconCache.js";

vi.mock("../../utils/websiteIcon.js", () => ({
  resolveIconCandidates: vi.fn(),
}));

vi.mock("../../utils/iconCache.js", () => ({
  loadIcon: vi.fn(),
}));

// alt="" is intentional (a decorative icon), which gives the <img> a
// "presentation" accessibility role rather than "img" — querying the DOM
// node directly instead of via getByRole/getByAltText.
function getIcon(container) {
  return container.querySelector("img");
}

function getPlaceholder(container) {
  return container.querySelector("span");
}

// vi.mock()'s factory-created mocks are shared across every test in this
// file — restoreAllMocks doesn't clear their call history (there's no
// original implementation to restore them to), so each test starts from a
// clean call count explicitly rather than relying on afterEach cleanup.
beforeEach(() => {
  vi.clearAllMocks();
});

describe("AssetIcon", () => {
  it("renders a same-sized blank placeholder with no candidates to try", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([]);

    const { container } = render(<AssetIcon ticker={null} website={null} size={24} />);

    expect(loadIcon).not.toHaveBeenCalled();
    expect(getIcon(container)).toBeNull();
    expect(getPlaceholder(container)).toHaveStyle({ width: "24px", height: "24px" });
  });

  it("renders a placeholder while the first candidate is still resolving", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
    ]);
    vi.mocked(loadIcon).mockReturnValue(new Promise(() => {})); // never resolves

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" size={24} />);

    expect(getIcon(container)).toBeNull();
    expect(getPlaceholder(container)).toHaveStyle({ width: "24px", height: "24px" });
  });

  it("renders the first candidate once loadIcon resolves it", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);
    vi.mocked(loadIcon).mockResolvedValue({
      src: "blob:https://equicast.test/cached-aapl",
      isObjectUrl: true,
    });

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute("src", "blob:https://equicast.test/cached-aapl")
    );
    expect(loadIcon).toHaveBeenCalledWith("https://cdn.brandfetch.io/ticker/AAPL?c=id");
  });

  it("falls through to the next candidate when one resolves to null", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
      "/icons/AAPL.svg",
    ]);
    vi.mocked(loadIcon).mockImplementation((url) =>
      url === "https://cdn.brandfetch.io/ticker/AAPL?c=id"
        ? Promise.resolve(null)
        : Promise.resolve({ src: url, isObjectUrl: false })
    );

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute(
        "src",
        "https://www.google.com/s2/favicons?domain=apple.com&sz=128"
      )
    );
  });

  it("renders a same-sized blank placeholder once every candidate resolves to null", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);
    vi.mocked(loadIcon).mockResolvedValue(null);

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" size={24} />);

    await waitFor(() => expect(loadIcon).toHaveBeenCalledTimes(2));
    expect(getIcon(container)).toBeNull();
    expect(getPlaceholder(container)).toHaveStyle({ width: "24px", height: "24px" });
  });

  it("falls through to the next candidate when a resolved source still fails to render", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);
    vi.mocked(loadIcon).mockImplementation((url) => Promise.resolve({ src: url, isObjectUrl: false }));

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute("src", "https://cdn.brandfetch.io/ticker/AAPL?c=id")
    );

    fireEvent.error(getIcon(container));

    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute(
        "src",
        "https://www.google.com/s2/favicons?domain=apple.com&sz=128"
      )
    );
  });

  it("resets the cascade when the ticker/website changes", async () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);
    vi.mocked(loadIcon).mockImplementation((url) =>
      url === "https://cdn.brandfetch.io/ticker/AAPL?c=id"
        ? Promise.resolve(null)
        : Promise.resolve({ src: url, isObjectUrl: false })
    );

    const { container, rerender } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);
    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute(
        "src",
        "https://www.google.com/s2/favicons?domain=apple.com&sz=128"
      )
    );

    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/MSFT?c=id",
      "https://www.google.com/s2/favicons?domain=microsoft.com&sz=128",
    ]);
    vi.mocked(loadIcon).mockImplementation((url) =>
      Promise.resolve({ src: url, isObjectUrl: false })
    );
    rerender(<AssetIcon ticker="MSFT" website="https://microsoft.com" />);

    await waitFor(() =>
      expect(getIcon(container)).toHaveAttribute("src", "https://cdn.brandfetch.io/ticker/MSFT?c=id")
    );
  });
});
