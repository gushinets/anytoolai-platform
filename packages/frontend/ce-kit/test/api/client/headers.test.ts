import { describe, expect, it } from "vitest";
import { buildHeaders } from "../../../src/api/client/headers";

describe("buildHeaders", () => {
  it("always sets Accept to application/json", () => {
    const headers = buildHeaders({}, undefined, undefined, false);
    expect(headers.get("Accept")).toBe("application/json");
  });

  it("sets Content-Type only when the request has a body", () => {
    expect(buildHeaders({}, undefined, undefined, false).has("Content-Type")).toBe(false);
    expect(buildHeaders({}, undefined, undefined, true).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it("does not overwrite an explicit Content-Type override", () => {
    const headers = buildHeaders({}, { "Content-Type": "text/plain" }, undefined, true);
    expect(headers.get("Content-Type")).toBe("text/plain");
  });

  it("sets X-Request-ID only when a requestId is provided", () => {
    expect(buildHeaders({}, undefined, undefined, false).has("X-Request-ID")).toBe(false);
    expect(buildHeaders({}, undefined, "req_1", false).get("X-Request-ID")).toBe("req_1");
  });

  it("does not overwrite an explicit X-Request-ID override", () => {
    const headers = buildHeaders({}, { "X-Request-ID": "req_override" }, "req_default", false);
    expect(headers.get("X-Request-ID")).toBe("req_override");
  });

  it("merges default headers with per-request overrides", () => {
    const headers = buildHeaders(
      { Authorization: "Bearer default" },
      { Authorization: "Bearer override", "X-Custom": "1" },
      undefined,
      false,
    );
    expect(headers.get("Authorization")).toBe("Bearer override");
    expect(headers.get("X-Custom")).toBe("1");
  });
});
