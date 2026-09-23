import { describe, expect, it } from "vitest";
import {
  collectFieldErrors,
  optionalTrimmedFieldError,
  requiredTrimmedFieldError,
} from "../src/products/runtime/fieldValidation";

describe("requiredTrimmedFieldError", () => {
  it("requires a non-empty, trimmed value within maxLength, as structured data (no prose)", () => {
    expect(requiredTrimmedFieldError("", 10)).toEqual({ code: "required" });
    expect(requiredTrimmedFieldError("  a", 10)).toEqual({ code: "outer_whitespace" });
    expect(requiredTrimmedFieldError("hello world", 5)).toEqual({ code: "max_length", maxLength: 5 });
    expect(requiredTrimmedFieldError("hello", 5)).toBeUndefined();
  });

  it("counts Unicode code points for maxLength, not UTF-16 code units", () => {
    // Code review finding: astral characters (many emoji) are 2 UTF-16 units each, so a naive
    // `.length` check would reject input the backend's code-point-counting JSON schema accepts.
    const twoEmoji = "\u{1F600}\u{1F600}"; // 2 code points, 4 UTF-16 units
    expect(requiredTrimmedFieldError(twoEmoji, 2)).toBeUndefined();
    expect(requiredTrimmedFieldError(twoEmoji, 1)).toEqual({ code: "max_length", maxLength: 1 });
  });
});

describe("optionalTrimmedFieldError", () => {
  it("treats an empty string as absent", () => {
    expect(optionalTrimmedFieldError("", 10)).toBeUndefined();
  });

  it("treats a whitespace-only value as absent too, not as a required-but-missing value", () => {
    // Code review finding: only `value.length === 0` was checked before, so "   " fell through to
    // requiredTrimmedFieldError and produced a "required" error.
    expect(optionalTrimmedFieldError("   ", 10)).toBeUndefined();
  });

  it("validates a genuinely non-empty value the same way requiredTrimmedFieldError does", () => {
    expect(optionalTrimmedFieldError("  Friday", 10)).toEqual({ code: "outer_whitespace" });
    expect(optionalTrimmedFieldError("Friday", 10)).toBeUndefined();
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
