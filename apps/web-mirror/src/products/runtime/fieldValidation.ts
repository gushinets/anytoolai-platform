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
  | { code: "max_length"; maxLength: number }
  | { code: "product"; key: string };

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
  if (trimBackendWhitespace(value).length === 0) {
    return { code: "required" };
  }
  return backendTrimmedLength(value) > maxLength ? { code: "max_length", maxLength } : undefined;
}

/** Optional counterpart of `requiredBackendTrimmedFieldError`: empty (after the backend trim) is fine,
 * otherwise only the length is checked. The product's `toInput` sends the trimmed value. */
export function optionalBackendTrimmedFieldError(value: string, maxLength: number): FieldError | undefined {
  return trimBackendWhitespace(value).length === 0 ? undefined : requiredBackendTrimmedFieldError(value, maxLength);
}

/** Length as the backend schema counts it: Unicode code points of the backend-trimmed text (not
 * UTF-16 units, not the raw value), so a counter agrees with `requiredBackendTrimmedFieldError`. */
export function backendTrimmedLength(value: string): number {
  return [...trimBackendWhitespace(value)].length;
}
