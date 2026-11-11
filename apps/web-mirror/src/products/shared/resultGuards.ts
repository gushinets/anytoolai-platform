export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function isOneOf<T extends string>(set: readonly T[], value: unknown): value is T {
  return typeof value === "string" && (set as readonly string[]).includes(value);
}
