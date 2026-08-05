import { describe, expect, it } from "vitest";
import type { AssertExactSchemaShape } from "../../src/api/driftAssertions";

describe("AssertExactSchemaShape", () => {
  it("accepts a shape that matches names, types, and nullability exactly", () => {
    type Backend = { limit_count: number; note: string | null; tag?: string };
    type Check = AssertExactSchemaShape<Backend, { limit_count: number; note: string | null; tag?: string }>;
    const check: Check = true;
    expect(check).toBe(true);
  });

  it("rejects a same-key type change, e.g. limit_count: number -> string", () => {
    type Backend = { limit_count: number };
    type Shape = { limit_count: string };
    type Check = AssertExactSchemaShape<Backend, Shape>;
    // @ts-expect-error limit_count type mismatch must fail typecheck, not silently pass.
    const check: Check = true;
    void check;
  });

  it("rejects a field that lost its nullability", () => {
    type Backend = { note: string | null };
    type Shape = { note: string };
    type Check = AssertExactSchemaShape<Backend, Shape>;
    // @ts-expect-error a dropped `| null` must fail typecheck.
    const check: Check = true;
    void check;
  });

  it("rejects a shape missing a backend field", () => {
    type Backend = { a: string; b: number };
    type Shape = { a: string };
    type Check = AssertExactSchemaShape<Backend, Shape>;
    // @ts-expect-error missing field `b` must fail typecheck.
    const check: Check = true;
    void check;
  });

  it("reports the missing key by name via the missingFromShape branch, proving it is reachable", () => {
    // `AssertExactSchemaShape` is intentionally unconstrained (`Shape extends object`) so this
    // branch can actually be reached -- a `Shape extends { [K in keyof T]: unknown }` constraint
    // would fail at the generic-instantiation site for a missing key, before this conditional's
    // body ever ran, leaving `{ missingFromShape: ... }` permanently dead code.
    type Backend = { a: string; b: number };
    type Shape = { a: string };
    type Check = AssertExactSchemaShape<Backend, Shape>;
    type ReportedMissingKey = Check extends { missingFromShape: infer K } ? K : never;
    const reported: ReportedMissingKey = "b";
    expect(reported).toBe("b");
  });

  it("rejects a shape with an extra field not on the backend schema", () => {
    type Backend = { a: string };
    type Shape = { a: string; extra: number };
    type Check = AssertExactSchemaShape<Backend, Shape>;
    // @ts-expect-error extra field `extra` must fail typecheck.
    const check: Check = true;
    void check;
  });
});
