import { describe, expect, it } from "vitest";
import {
  collectFieldErrors,
  optionalTrimmedFieldError,
  requiredTrimmedFieldError,
} from "../src/products/runtime/fieldValidation";

describe("requiredTrimmedFieldError", () => {
  it("requires a non-empty, trimmed value within maxLength", () => {
    expect(requiredTrimmedFieldError("", "Notes", 10)).toBe("Notes is required.");
    expect(requiredTrimmedFieldError("  a", "Notes", 10)).toBe("Notes must not start or end with whitespace.");
    expect(requiredTrimmedFieldError("hello world", "Notes", 5)).toBe("Notes must be 5 characters or fewer.");
    expect(requiredTrimmedFieldError("hello", "Notes", 5)).toBeUndefined();
  });

  it("counts Unicode code points for maxLength, not UTF-16 code units", () => {
    // Code review finding: astral characters (many emoji) are 2 UTF-16 units each, so a naive
    // `.length` check would reject input the backend's code-point-counting JSON schema accepts.
    const twoEmoji = "\u{1F600}\u{1F600}"; // 2 code points, 4 UTF-16 units
    expect(requiredTrimmedFieldError(twoEmoji, "Notes", 2)).toBeUndefined();
    expect(requiredTrimmedFieldError(twoEmoji, "Notes", 1)).toBe("Notes must be 1 characters or fewer.");
  });
});

describe("optionalTrimmedFieldError", () => {
  it("treats an empty string as absent", () => {
    expect(optionalTrimmedFieldError("", "Due date", 10)).toBeUndefined();
  });

  it("treats a whitespace-only value as absent too, not as a required-but-missing value", () => {
    // Code review finding: only `value.length === 0` was checked before, so "   " fell through to
    // requiredTrimmedFieldError and produced "Due date is required."
    expect(optionalTrimmedFieldError("   ", "Due date", 10)).toBeUndefined();
  });

  it("validates a genuinely non-empty value the same way requiredTrimmedFieldError does", () => {
    expect(optionalTrimmedFieldError("  Friday", "Due date", 10)).toBe(
      "Due date must not start or end with whitespace.",
    );
    expect(optionalTrimmedFieldError("Friday", "Due date", 10)).toBeUndefined();
  });
});

describe("collectFieldErrors", () => {
  it("keeps only the entries with a defined error", () => {
    expect(
      collectFieldErrors<{ a: string; b: string }>([
        ["a", "A is required."],
        ["b", undefined],
      ]),
    ).toEqual({ a: "A is required." });
  });
});
