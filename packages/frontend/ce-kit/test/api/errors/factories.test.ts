import { describe, expect, it } from "vitest";
import {
  abortedError,
  backendError,
  invalidResponseError,
  networkError,
  timeoutError,
} from "../../../src/api/errors/factories";

describe("error union factories", () => {
  it("builds a stable backend_error", () => {
    const error = backendError(404, {
      code: "product_not_found",
      message: "Product not found",
      requestId: "req_123",
    });
    expect(error).toEqual({
      type: "backend_error",
      status: 404,
      code: "product_not_found",
      message: "Product not found",
      requestId: "req_123",
    });
  });

  it("builds network_error, timeout, aborted, and invalid_response variants", () => {
    expect(networkError()).toEqual({ type: "network_error", message: "Network request failed." });
    expect(timeoutError()).toEqual({ type: "timeout" });
    expect(abortedError()).toEqual({ type: "aborted" });
    expect(invalidResponseError(200)).toEqual({
      type: "invalid_response",
      status: 200,
      message: "Response could not be parsed.",
    });
  });

  it("does not leak raw response content into invalid_response messages by default", () => {
    const error = invalidResponseError(500);
    expect(error.message).not.toContain("<html>");
  });
});
