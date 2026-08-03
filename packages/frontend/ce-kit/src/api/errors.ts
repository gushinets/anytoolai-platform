/**
 * Stable, frontend-safe error union for all Platform API calls.
 *
 * Every variant is safe to log, display, or forward as-is: none of them carry raw response
 * bodies, headers, or other unvalidated backend content beyond the three fields the backend
 * envelope explicitly promises (code, message, request_id).
 */
export type PlatformApiError =
  | BackendApiError
  | NetworkApiError
  | TimeoutApiError
  | AbortedApiError
  | InvalidResponseApiError;

export type PlatformApiErrorType = PlatformApiError["type"];

export type BackendApiError = {
  type: "backend_error";
  status: number;
  code: string;
  message: string;
  requestId: string;
};

export type NetworkApiError = {
  type: "network_error";
  message: string;
};

export type TimeoutApiError = {
  type: "timeout";
};

export type AbortedApiError = {
  type: "aborted";
};

export type InvalidResponseApiError = {
  type: "invalid_response";
  status: number;
  message: string;
};

export function backendError(
  status: number,
  detail: BackendErrorDetail,
): BackendApiError {
  return {
    type: "backend_error",
    status,
    code: detail.code,
    message: detail.message,
    requestId: detail.requestId,
  };
}

export function networkError(message = "Network request failed."): NetworkApiError {
  return { type: "network_error", message };
}

export function timeoutError(): TimeoutApiError {
  return { type: "timeout" };
}

export function abortedError(): AbortedApiError {
  return { type: "aborted" };
}

export function invalidResponseError(
  status: number,
  message = "Response could not be parsed.",
): InvalidResponseApiError {
  return { type: "invalid_response", status, message };
}

export type BackendErrorDetail = {
  code: string;
  message: string;
  requestId: string;
};

/**
 * Validates the backend's `{ error: { code, message, request_id } }` envelope and extracts only
 * those three known-safe fields. Returns null for anything that doesn't match the shape, so
 * callers fall back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseBackendErrorEnvelope(payload: unknown): BackendErrorDetail | null {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) {
    return null;
  }

  const error = (payload as { error: unknown }).error;
  if (typeof error !== "object" || error === null) {
    return null;
  }

  const { code, message, request_id: requestId } = error as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string" || typeof requestId !== "string") {
    return null;
  }

  return { code, message, requestId };
}
