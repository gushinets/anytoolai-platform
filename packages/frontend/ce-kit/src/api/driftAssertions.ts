/**
 * Compile-time assertion that `Keys` names every property of the generated OpenAPI schema type
 * `T` -- used next to hand-maintained parsers (parseGuestIdentityPayload, parseRuntimeConfig) so
 * that regenerating `platformApi.ts` from a changed backend schema fails typecheck instead of
 * silently leaving those parsers stale. `Keys extends readonly (keyof T)[]` already rejects keys
 * that don't belong to `T`; this checks the reverse direction (nothing from `T` left out).
 *
 * This only covers property *names*. It does not catch a same-key type or nullability change
 * (e.g. `limit_count: number -> string`, or a field losing its `| null`) -- for that, use
 * `AssertExactSchemaShape` below.
 */
export type AssertExactSchemaKeys<T extends object, Keys extends readonly (keyof T)[]> =
  Exclude<keyof T, Keys[number]> extends never
    ? true
    : { missingFromParser: Exclude<keyof T, Keys[number]> };

/**
 * Strict type equality (distinct from mutual assignability): catches differences that `A extends
 * B ? B extends A ? ... ` would miss, such as `unknown` vs `any`, or a lost `| null` union member,
 * by comparing how each type distributes over a conditional instead of comparing assignability
 * directly.
 */
type IsEqual<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
  ? true
  : false;

/**
 * Names of `T`'s properties that `Shape` doesn't declare at all. Deliberately unconstrained
 * (`Shape extends object`, not `Shape extends { [K in keyof T]: unknown }`) -- a constraint
 * requiring `Shape` to already have every key of `T` would make this branch of
 * `AssertExactSchemaShape` unreachable, since the missing-key case would fail at the generic
 * instantiation site instead of ever reaching this check.
 */
type MissingShapeKeys<T extends object, Shape extends object> = {
  [K in keyof T]-?: K extends keyof Shape ? never : K;
}[keyof T];

/** Names of `Shape`'s properties that don't correspond to any property of `T`. */
type ExtraShapeKeys<T extends object, Shape extends object> = {
  [K in keyof Shape]-?: K extends keyof T ? never : K;
}[keyof Shape];

/**
 * Whether `K` is an optional property of `T`. `{} extends Pick<T, K>` is true exactly when picking
 * just that one property still allows an empty object -- i.e. the property can be omitted.
 */
// eslint-disable-next-line @typescript-eslint/no-empty-object-type -- deliberate: `{}` is the "no required properties" check the optionality test relies on, not an accidental any-value type.
type IsOptionalKey<T extends object, K extends keyof T> = {} extends Pick<T, K> ? true : false;

/**
 * Names of `T`'s properties that `Shape` does declare, but with a different type, or a different
 * optionality (e.g. `backend?: string` vs `backend: string | undefined`) -- `IsEqual<T[K],
 * Shape[K]>` alone can't tell these apart, since indexing an optional property already produces
 * `... | undefined` independent of the mapped type's own `-?` modifier. Only meaningful once
 * `MissingShapeKeys` is empty -- `K extends keyof Shape` is re-checked per key so this stays safe
 * to evaluate even when some keys are missing.
 */
type MismatchedShapeKeys<T extends object, Shape extends object> = {
  [K in keyof T]-?: K extends keyof Shape
    ? IsEqual<T[K], Shape[K]> extends true
      ? IsOptionalKey<T, K> extends IsOptionalKey<Shape, K>
        ? never
        : K
      : K
    : never;
}[keyof T];

/**
 * Compile-time assertion that hand-maintained `Shape` matches the generated OpenAPI schema type
 * `T` field-for-field: same property names AND same type (including nullability/optionality) for
 * each. Put next to a parser as `type _Check = AssertExactSchemaShape<Backend["Foo"], { field:
 * string; other: number | null }>` so a backend schema change such as `limit_count: number ->
 * string`, or a field losing its `| null`, fails typecheck at the assertion site instead of
 * silently leaving the parser's runtime type guards stale.
 */
export type AssertExactSchemaShape<T extends object, Shape extends object> =
  MissingShapeKeys<T, Shape> extends never
    ? ExtraShapeKeys<T, Shape> extends never
      ? MismatchedShapeKeys<T, Shape> extends never
        ? true
        : { typeMismatch: MismatchedShapeKeys<T, Shape> }
      : { extraInShape: ExtraShapeKeys<T, Shape> }
    : { missingFromShape: MissingShapeKeys<T, Shape> };
