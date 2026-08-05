/**
 * Stable, frontend-safe error union for all Platform API calls.
 *
 * Every variant is safe to log, display, or forward as-is: none of them carry raw response
 * bodies, headers, or other unvalidated backend content beyond the three fields the backend
 * envelope explicitly promises (code, message, request_id) -- see ./envelope.ts.
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
