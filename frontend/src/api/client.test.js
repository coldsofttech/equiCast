import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "./client.js";

function jsonResponse(body, status = 200, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
    headers: new Headers(headers),
  };
}

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("GETs the given path under the default /api base, with no body", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));

    await apiFetch("/identity/me/");

    expect(fetch).toHaveBeenCalledWith(
      "/api/identity/me/",
      expect.objectContaining({ method: "GET", body: undefined })
    );
  });

  it("attaches a bearer token when getAccessToken is given", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    const getAccessToken = vi.fn().mockResolvedValue("token-123");

    await apiFetch("/identity/me/", { getAccessToken });

    const [, init] = fetch.mock.calls[0];
    expect(init.headers.get("Authorization")).toBe("Bearer token-123");
  });

  it("omits the Authorization header when no getAccessToken is given", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ ok: true }));

    await apiFetch("/market/stock/AAPL/profile/");

    const [, init] = fetch.mock.calls[0];
    expect(init.headers.has("Authorization")).toBe(false);
  });

  it("JSON-encodes a plain object body and sets Content-Type", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ id: "1" }, 201));

    await apiFetch("/accounts/", { method: "POST", body: { name: "ISA" } });

    const [, init] = fetch.mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ name: "ISA" }));
    expect(init.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns null for a 204 response", async () => {
    fetch.mockResolvedValueOnce({ ok: true, status: 204 });

    const result = await apiFetch("/holdings/h-1/", { method: "DELETE" });

    expect(result).toBeNull();
  });

  it("returns the parsed JSON body for a successful response", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ user_id: "auth0|abc", default_currency: "GBP" }));

    const result = await apiFetch("/identity/me/");

    expect(result).toEqual({ user_id: "auth0|abc", default_currency: "GBP" });
  });

  it("throws an ApiError with the response's detail and status on failure", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "Unknown asset class 'crypto'." }, 400));

    await expect(apiFetch("/market/crypto/BTC/profile/")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      message: "Unknown asset class 'crypto'.",
    });
  });

  it("falls back to statusText when the error body isn't JSON", async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });

    await expect(apiFetch("/identity/me/")).rejects.toMatchObject({
      status: 500,
      message: "Internal Server Error",
    });
  });

  it("is a real ApiError instance", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "nope" }, 404));

    try {
      await apiFetch("/accounts/missing/");
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
    }
  });

  it("parses Retry-After into retryAfterSeconds on a 429", async () => {
    fetch.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Request was throttled. Expected available in 46 seconds." },
        429,
        { "Retry-After": "46" }
      )
    );

    await expect(apiFetch("/identity/me/")).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: 46,
    });
  });

  it("leaves retryAfterSeconds null when a 429 has no Retry-After header", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "throttled" }, 429));

    await expect(apiFetch("/identity/me/")).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: null,
    });
  });

  it("ignores a Retry-After header on a non-429 error", async () => {
    // A Retry-After header outside a 429 isn't the "you're rate limited"
    // signal this field means, so it's deliberately not parsed even if a
    // server happened to send one for some other status.
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "nope" }, 400, { "Retry-After": "46" }));

    await expect(apiFetch("/accounts/")).rejects.toMatchObject({
      status: 400,
      retryAfterSeconds: null,
    });
  });
});
