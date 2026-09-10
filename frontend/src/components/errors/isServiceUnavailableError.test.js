import { describe, expect, it } from "vitest";
import isServiceUnavailableError from "./isServiceUnavailableError.js";

describe("isServiceUnavailableError", () => {
  it("is true for a network failure with no HTTP status at all", () => {
    expect(isServiceUnavailableError(null)).toBe(true);
    expect(isServiceUnavailableError(undefined)).toBe(true);
  });

  it("is true for a genuine 5xx", () => {
    expect(isServiceUnavailableError(500)).toBe(true);
    expect(isServiceUnavailableError(502)).toBe(true);
    expect(isServiceUnavailableError(503)).toBe(true);
  });

  it("is false for a 4xx, including 429", () => {
    expect(isServiceUnavailableError(400)).toBe(false);
    expect(isServiceUnavailableError(403)).toBe(false);
    expect(isServiceUnavailableError(404)).toBe(false);
    expect(isServiceUnavailableError(429)).toBe(false);
  });
});
