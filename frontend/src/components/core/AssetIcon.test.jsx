import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AssetIcon from "./AssetIcon.jsx";
import { resolveIconCandidates } from "../../utils/websiteIcon.js";

vi.mock("../../utils/websiteIcon.js", () => ({
  resolveIconCandidates: vi.fn(),
}));

// alt="" is intentional (a decorative icon), which gives the <img> a
// "presentation" accessibility role rather than "img" — querying the DOM
// node directly instead of via getByRole/getByAltText.
function getIcon(container) {
  return container.querySelector("img");
}

describe("AssetIcon", () => {
  it("renders nothing with no candidates to try", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([]);

    const { container } = render(<AssetIcon ticker={null} website={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders the first candidate (Brandfetch) initially", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    expect(getIcon(container)).toHaveAttribute("src", "https://cdn.brandfetch.io/ticker/AAPL?c=id");
  });

  it("falls through to the next candidate when one fails to load", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
      "/icons/AAPL.svg",
    ]);

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    fireEvent.error(getIcon(container));
    expect(getIcon(container)).toHaveAttribute(
      "src",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128"
    );

    fireEvent.error(getIcon(container));
    expect(getIcon(container)).toHaveAttribute("src", "/icons/AAPL.svg");
  });

  it("renders nothing once every candidate has failed", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);

    const { container } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);

    fireEvent.error(getIcon(container));
    fireEvent.error(getIcon(container));

    expect(container).toBeEmptyDOMElement();
  });

  it("resets the cascade when the ticker/website changes", () => {
    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/AAPL?c=id",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]);

    const { container, rerender } = render(<AssetIcon ticker="AAPL" website="https://apple.com" />);
    fireEvent.error(getIcon(container));
    expect(getIcon(container)).toHaveAttribute(
      "src",
      "https://www.google.com/s2/favicons?domain=apple.com&sz=128"
    );

    vi.mocked(resolveIconCandidates).mockReturnValue([
      "https://cdn.brandfetch.io/ticker/MSFT?c=id",
      "https://www.google.com/s2/favicons?domain=microsoft.com&sz=128",
    ]);
    rerender(<AssetIcon ticker="MSFT" website="https://microsoft.com" />);

    expect(getIcon(container)).toHaveAttribute("src", "https://cdn.brandfetch.io/ticker/MSFT?c=id");
  });
});
