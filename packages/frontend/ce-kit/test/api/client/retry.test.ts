import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { assertRetryAllowed, delay, isAmbiguousFailure, isRetryable } from "../../../src/api/client/retry";

describe("assertRetryAllowed", () => {
  it("allows a retry policy on GET", () => {
    expect(() => assertRetryAllowed("GET", "/v1/x", { attempts: 2 })).not.toThrow();
  });

  it("allows no retry policy on any method", () => {
    for (const method of ["GET", "POST", "PUT", "PATCH", "DELETE"] as const) {
      expect(() => assertRetryAllowed(method, "/v1/x", undefined)).not.toThrow();
    }
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"] as const)(
    "throws when a retry policy is set on %s",
    (method) => {
      expect(() => assertRetryAllowed(method, "/v1/x", { attempts: 2 })).toThrow(
        /retry is only supported for safe GET/,
      );
    },
  );
});

describe("isRetryable", () => {
  it("is retryable for network_error and timeout", () => {
    expect(isRetryable({ type: "network_error", message: "boom" })).toBe(true);
    expect(isRetryable({ type: "timeout" })).toBe(true);
  });

  it("is not retryable for aborted, backend_error, or invalid_response", () => {
    expect(isRetryable({ type: "aborted" })).toBe(false);
    expect(
      isRetryable({
        type: "backend_error",
        status: 500,
        code: "internal_error",
        message: "boom",
        requestId: "req_1",
      }),
    ).toBe(false);
    expect(isRetryable({ type: "invalid_response", status: 200, message: "bad shape" })).toBe(
      false,
    );
  });
});

describe("delay", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves after the given duration when not cancelled", async () => {
    const spy = vi.fn();
    void delay(1000).then(spy);

    await vi.advanceTimersByTimeAsync(999);
    expect(spy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(spy).toHaveBeenCalled();
  });

  it("resolves immediately when the signal aborts before the duration elapses", async () => {
    const controller = new AbortController();
    const spy = vi.fn();
    void delay(10_000, controller.signal).then(spy);

    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await vi.advanceTimersByTimeAsync(0);

    expect(spy).toHaveBeenCalled();
  });

  it("resolves immediately when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const spy = vi.fn();
    void delay(10_000, controller.signal).then(spy);

    await vi.advanceTimersByTimeAsync(0);
    expect(spy).toHaveBeenCalled();
  });
});

describe("isAmbiguousFailure", () => {
  it("is true where the backend may already have acted: network, timeout and 5xx", () => {
    expect(isAmbiguousFailure({ type: "network_error", message: "boom" })).toBe(true);
    expect(isAmbiguousFailure({ type: "timeout" })).toBe(true);
    expect(
      isAmbiguousFailure({ type: "backend_error", status: 502, code: "bad_gateway", message: "x", requestId: "r" }),
    ).toBe(true);
  });

  it("is true for a 5xx without the error envelope (a proxy's HTML 502, an empty 503)", () => {
    expect(isAmbiguousFailure({ type: "invalid_response", status: 502, message: "x" })).toBe(true);
    expect(isAmbiguousFailure({ type: "invalid_response", status: 503, message: "x" })).toBe(true);
  });

  it("is false for a definite 4xx, an aborted request and an unparsable 2xx or 4xx", () => {
    expect(
      isAmbiguousFailure({ type: "backend_error", status: 422, code: "invalid", message: "x", requestId: "r" }),
    ).toBe(false);
    expect(isAmbiguousFailure({ type: "aborted" })).toBe(false);
    expect(isAmbiguousFailure({ type: "invalid_response", status: 200, message: "x" })).toBe(false);
    expect(isAmbiguousFailure({ type: "invalid_response", status: 404, message: "x" })).toBe(false);
  });
});
