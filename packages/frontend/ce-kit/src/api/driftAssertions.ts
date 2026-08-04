/**
 * Compile-time assertion that `Keys` names every property of the generated OpenAPI schema type
 * `T` -- used next to hand-maintained parsers (parseGuestIdentityPayload, parseRuntimeConfig) so
 * that regenerating `platformApi.ts` from a changed backend schema fails typecheck instead of
 * silently leaving those parsers stale. `Keys extends readonly (keyof T)[]` already rejects keys
 * that don't belong to `T`; this checks the reverse direction (nothing from `T` left out).
 */
export type AssertExactSchemaKeys<T extends object, Keys extends readonly (keyof T)[]> =
  Exclude<keyof T, Keys[number]> extends never
    ? true
    : { missingFromParser: Exclude<keyof T, Keys[number]> };
