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
