import { describe, expect, it } from "vitest";
import { parseBackendErrorEnvelope } from "../../../src/api/errors/envelope";

describe("parseBackendErrorEnvelope", () => {
  it("extracts code, message, and requestId from a well-formed envelope", () => {
    const detail = parseBackendErrorEnvelope({
      error: { code: "product_not_found", message: "Product not found", request_id: "req_123" },
    });

    expect(detail).toEqual({
      code: "product_not_found",
      message: "Product not found",
      requestId: "req_123",
    });
  });

  it.each([
    ["non-object payload", "not an object"],
    ["null payload", null],
    ["missing error key", {}],
    ["error is not an object", { error: "oops" }],
    ["error is null", { error: null }],
    ["missing code", { error: { message: "m", request_id: "r" } }],
    ["missing message", { error: { code: "c", request_id: "r" } }],
    ["missing request_id", { error: { code: "c", message: "m" } }],
    ["non-string code", { error: { code: 1, message: "m", request_id: "r" } }],
  ])("returns null for %s", (_label, payload) => {
    expect(parseBackendErrorEnvelope(payload)).toBeNull();
  });

  it("extracts only the known-safe fields, ignoring unrelated payload content", () => {
    const detail = parseBackendErrorEnvelope({
      error: { code: "c", message: "m", request_id: "r" },
      secret_debug_dump: "leak",
    });
    expect(detail).toEqual({ code: "c", message: "m", requestId: "r" });
  });
});
