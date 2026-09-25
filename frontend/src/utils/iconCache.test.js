import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadIcon } from "./iconCache.js";
import { readIconValue, writeIconValue } from "./marketDataCache.js";

vi.mock("./marketDataCache.js", () => ({
  readIconValue: vi.fn(),
  writeIconValue: vi.fn(),
}));

const URL_UNDER_TEST = "https://cdn.brandfetch.io/ticker/AAPL?c=id";

function imageResponse(blob, { ok = true, status = 200, contentType = "image/png" } = {}) {
  return {
    ok,
    status,
    headers: new Headers(contentType ? { "content-type": contentType } : {}),
    blob: async () => blob,
  };
}

beforeEach(() => {
  // vi.mock()'s factory-created mocks (readIconValue/writeIconValue) are
  // shared across every test in this file — restoreAllMocks doesn't clear
  // their call history, so each test starts from a clean slate explicitly.
  vi.clearAllMocks();
  global.fetch = vi.fn();
  // jsdom doesn't implement the Blob URL Store — stubbed the same way this
  // suite stubs any other browser API jsdom leaves unimplemented.
  URL.createObjectURL = vi.fn((blob) => `blob:mock/${blob.size}`);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("loadIcon", () => {
  it("returns an object URL from a cache hit without calling fetch", async () => {
    const cachedBlob = new Blob(["cached"], { type: "image/png" });
    vi.mocked(readIconValue).mockResolvedValue(cachedBlob);

    const result = await loadIcon(URL_UNDER_TEST);

    expect(fetch).not.toHaveBeenCalled();
    expect(result).toEqual({ src: `blob:mock/${cachedBlob.size}`, isObjectUrl: true });
  });

  it("fetches, caches, and returns an object URL on a cache miss", async () => {
    vi.mocked(readIconValue).mockResolvedValue(null);
    const fetchedBlob = new Blob(["fetched"], { type: "image/png" });
    fetch.mockResolvedValueOnce(imageResponse(fetchedBlob));

    const result = await loadIcon(URL_UNDER_TEST);

    expect(fetch).toHaveBeenCalledWith(URL_UNDER_TEST, { mode: "cors", credentials: "omit" });
    expect(writeIconValue).toHaveBeenCalledWith(URL_UNDER_TEST, fetchedBlob);
    expect(result).toEqual({ src: `blob:mock/${fetchedBlob.size}`, isObjectUrl: true });
  });

  it("returns null (cascade to the next candidate) on a non-OK response", async () => {
    vi.mocked(readIconValue).mockResolvedValue(null);
    fetch.mockResolvedValueOnce(imageResponse(new Blob(), { ok: false, status: 401 }));

    const result = await loadIcon(URL_UNDER_TEST);

    expect(writeIconValue).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("returns null when the response isn't actually an image", async () => {
    vi.mocked(readIconValue).mockResolvedValue(null);
    fetch.mockResolvedValueOnce(imageResponse(new Blob(), { contentType: "text/html" }));

    const result = await loadIcon(URL_UNDER_TEST);

    expect(writeIconValue).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("falls back to the raw URL, uncached, when fetch rejects (network error or CORS block)", async () => {
    vi.mocked(readIconValue).mockResolvedValue(null);
    fetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await loadIcon(URL_UNDER_TEST);

    expect(writeIconValue).not.toHaveBeenCalled();
    expect(result).toEqual({ src: URL_UNDER_TEST, isObjectUrl: false });
  });
});
