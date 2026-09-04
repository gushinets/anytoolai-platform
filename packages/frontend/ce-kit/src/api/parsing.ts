/**
 * Shared structural guards for hand-written backend response parsers (`parseQuotaState`,
 * `parseScenarioSessionSnapshot`, `parseRuntimeConfig`, ...). Centralized so a future fix to
 * either check (e.g. rejecting arrays, which `typeof [] === "object"` currently lets through
 * `isRecord`) only has to be made once.
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/** True for a field that's optional-and-nullable on the wire: absent, explicit null, or a string. */
export function isNullableString(value: unknown): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

/**
 * Builds a runtime membership guard for a generated closed-set string union `T` from an
 * exhaustive value map. `values` is typed `Record<T, true>`, so the call site itself -- not just
 * this helper -- fails to typecheck if `T` gains or loses a member and the map isn't updated to
 * match, the same compile-time completeness every hand-written `isX()` guard in ce-kit relied on
 * before they shared this helper.
 */
export function makeEnumGuard<T extends string>(
  values: Record<T, true>,
): (value: string) => value is T {
  return (value: string): value is T => Object.hasOwn(values, value);
}
