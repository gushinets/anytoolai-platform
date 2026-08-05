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
