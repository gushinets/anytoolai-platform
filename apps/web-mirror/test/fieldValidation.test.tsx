import { describe, expect, it } from "vitest";
import {
  collectFieldErrors,
  backendTrimmedLength,
  optionalBackendTrimmedFieldError,
  requiredBackendTrimmedFieldError,
} from "../src/products/runtime/fieldValidation";

describe("requiredBackendTrimmedFieldError", () => {
  it("requires non-empty text after the backend trim, as structured data (no prose)", () => {
    expect(requiredBackendTrimmedFieldError("", 10)).toEqual({ code: "required" });
    expect(requiredBackendTrimmedFieldError(" \n ", 10)).toEqual({ code: "required" });
    expect(requiredBackendTrimmedFieldError("  hello\n", 5)).toBeUndefined();
    expect(requiredBackendTrimmedFieldError("hello world", 5)).toEqual({ code: "max_length", maxLength: 5 });
  });

  it("counts Unicode code points for maxLength, not UTF-16 code units", () => {
    // Astral characters (many emoji) are 2 UTF-16 units each; the backend schema counts code points.
    const twoEmoji = "\u{1F600}\u{1F600}"; // 2 code points, 4 UTF-16 units
    expect(requiredBackendTrimmedFieldError(twoEmoji, 2)).toBeUndefined();
    expect(requiredBackendTrimmedFieldError(twoEmoji, 1)).toEqual({ code: "max_length", maxLength: 1 });
    expect(backendTrimmedLength(twoEmoji)).toBe(2);
    expect(backendTrimmedLength("  ab\n")).toBe(2);
  });
});

describe("collectFieldErrors", () => {
  it("keeps only the entries with a defined error", () => {
    expect(
      collectFieldErrors<{ a: string; b: string }>([
        ["a", { code: "required" }],
        ["b", undefined],
      ]),
    ).toEqual({ a: { code: "required" } });
  });
});

describe("optionalBackendTrimmedFieldError", () => {
  it("accepts empty or outer-whitespace-only values and pasted padding, checks only the length", () => {
    expect(optionalBackendTrimmedFieldError("", 5)).toBeUndefined();
    expect(optionalBackendTrimmedFieldError(" \n\u00a0 ", 5)).toBeUndefined();
    expect(optionalBackendTrimmedFieldError("  abc\n", 5)).toBeUndefined();
    expect(optionalBackendTrimmedFieldError("abcdef", 5)).toEqual({ code: "max_length", maxLength: 5 });
  });
});
