/**
 * Client-side field validation shared by every product's `validate()` (backend schema validation
 * stays authoritative either way -- these only give immediate form feedback). Extracted once a
 * second product (Client Update Writer) reimplemented the exact same trimmed-required-field /
 * trimmed-optional-field / two-line error-set pattern ProposalAI already had (code review finding).
 */

/**
 * What is wrong with a field, as data: the UI renders the message in the current UI locale
 * (`FieldErrorMessage`), so a validator never returns English prose. `product` carries a key into
 * the product's own message namespace for product-specific rules.
 */
export type FieldError =
  | { code: "required" }
  | { code: "outer_whitespace" }
  | { code: "max_length"; maxLength: number }
  | { code: "product"; key: string };

/** Shared by requiredTrimmedFieldError/optionalTrimmedFieldError once they've each already
 * decided the (already-trimmed) value counts as "present" -- takes `trimmed` as a parameter
 * rather than recomputing `value.trim()` itself, so a call through either public function trims
 * the value exactly once (code review finding: the two used to trim it twice between them). */
function trimmedFieldError(value: string, trimmed: string, maxLength: number): FieldError | undefined {
  if (value !== trimmed) {
    return { code: "outer_whitespace" };
  }
  // Code review finding: `.length` counts UTF-16 code units, but the backend JSON schema's
  // `maxLength` counts Unicode code points -- a surrogate-pair character (e.g. many emoji) counts
  // as 2 here but 1 there, which would reject input the backend actually accepts. `[...value]`
  // iterates by code point.
  if ([...value].length > maxLength) {
    return { code: "max_length", maxLength };
  }
  return undefined;
}

/** Mirrors a `^\S([\s\S]*\S)?(?!\n)$` schema pattern (no leading/trailing whitespace)
 * structurally, instead of transcribing the regex itself. */
export function requiredTrimmedFieldError(value: string, maxLength: number): FieldError | undefined {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return { code: "required" };
  }
  return trimmedFieldError(value, trimmed, maxLength);
}

// Code review finding: a whitespace-only value (e.g. "   ") has length > 0, so it used to fall
// through to requiredTrimmedFieldError and get flagged "is required" for what should be treated
// as an empty optional field -- `.trim()` first so only genuine content counts as "present".
export function optionalTrimmedFieldError(value: string, maxLength: number): FieldError | undefined {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return undefined;
  }
  return trimmedFieldError(value, trimmed, maxLength);
}

/** Collapses a product's per-field `if (error) errors.field = error;` repetition into one call:
 * `collectFieldErrors([["field", someFieldError(...)], ...])`. */
export function collectFieldErrors<V extends Record<string, unknown>>(
  entries: ReadonlyArray<readonly [keyof V, FieldError | undefined]>,
): Partial<Record<keyof V, FieldError>> {
  const errors: Partial<Record<keyof V, FieldError>> = {};
  for (const [field, error] of entries) {
    if (error) {
      errors[field] = error;
    }
  }
  return errors;
}

/** Python `re` `\s` (the backend's `^\S([\s\S]*\S)?(?!\n)$` text-field pattern) for a str: Unicode White_Space-ish set plus
 * U+001C-U+001F and U+0085, and *not* U+FEFF. JS `trim()` differs on exactly those code points, so
 * the client must not use it for these fields. */
const BACKEND_WHITESPACE = "\\t\\n\\v\\f\\r \\u001c-\\u001f\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const OUTER_BACKEND_WHITESPACE = new RegExp(`^[${BACKEND_WHITESPACE}]+|[${BACKEND_WHITESPACE}]+$`, "g");

/** Text exactly as the backend's pattern accepts it: outer whitespace removed, inner text untouched. */
export function trimBackendWhitespace(value: string): string {
  return value.replace(OUTER_BACKEND_WHITESPACE, "");
}

/** For pasted long-text fields (a trailing newline is the common case): the value is trimmed with
 * `trimBackendWhitespace`, not rejected, so the product's `toInput` must send the trimmed value. */
export function requiredBackendTrimmedFieldError(value: string, maxLength: number): FieldError | undefined {
  const trimmed = trimBackendWhitespace(value);
  if (trimmed.length === 0) {
    return { code: "required" };
  }
  return [...trimmed].length > maxLength ? { code: "max_length", maxLength } : undefined;
}
