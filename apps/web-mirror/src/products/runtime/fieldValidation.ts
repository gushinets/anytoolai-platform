/**
 * Client-side field validation shared by every product's `validate()` (backend schema validation
 * stays authoritative either way -- these only give immediate form feedback). Extracted once a
 * second product (Client Update Writer) reimplemented the exact same trimmed-required-field /
 * trimmed-optional-field / two-line error-set pattern ProposalAI already had (code review finding).
 */

/** Shared by requiredTrimmedFieldError/optionalTrimmedFieldError once they've each already
 * decided the (already-trimmed) value counts as "present" -- takes `trimmed` as a parameter
 * rather than recomputing `value.trim()` itself, so a call through either public function trims
 * the value exactly once (code review finding: the two used to trim it twice between them). */
function trimmedFieldError(value: string, trimmed: string, label: string, maxLength: number): string | undefined {
  if (value !== trimmed) {
    return `${label} must not start or end with whitespace.`;
  }
  // Code review finding: `.length` counts UTF-16 code units, but the backend JSON schema's
  // `maxLength` counts Unicode code points -- a surrogate-pair character (e.g. many emoji) counts
  // as 2 here but 1 there, which would reject input the backend actually accepts. `[...value]`
  // iterates by code point.
  if ([...value].length > maxLength) {
    return `${label} must be ${maxLength} characters or fewer.`;
  }
  return undefined;
}

/** Mirrors a `^\S([\s\S]*\S)?(?!\n)$` schema pattern (no leading/trailing whitespace)
 * structurally, instead of transcribing the regex itself. */
export function requiredTrimmedFieldError(value: string, label: string, maxLength: number): string | undefined {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return `${label} is required.`;
  }
  return trimmedFieldError(value, trimmed, label, maxLength);
}

// Code review finding: a whitespace-only value (e.g. "   ") has length > 0, so it used to fall
// through to requiredTrimmedFieldError and get flagged "is required" for what should be treated
// as an empty optional field -- `.trim()` first so only genuine content counts as "present".
export function optionalTrimmedFieldError(value: string, label: string, maxLength: number): string | undefined {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return undefined;
  }
  return trimmedFieldError(value, trimmed, label, maxLength);
}

/** Collapses a product's per-field `if (error) errors.field = error;` repetition into one call:
 * `collectFieldErrors([["field", someFieldError(...)], ...])`. */
export function collectFieldErrors<V extends Record<string, unknown>>(
  entries: ReadonlyArray<readonly [keyof V, string | undefined]>,
): Partial<Record<keyof V, string>> {
  const errors: Partial<Record<keyof V, string>> = {};
  for (const [field, error] of entries) {
    if (error) {
      errors[field] = error;
    }
  }
  return errors;
}
