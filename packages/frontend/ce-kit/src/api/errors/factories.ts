import type { BackendErrorDetail } from "./envelope";
import type {
  AbortedApiError,
  BackendApiError,
  InvalidResponseApiError,
  NetworkApiError,
  TimeoutApiError,
} from "./types";

export function backendError(status: number, detail: BackendErrorDetail): BackendApiError {
  return {
    type: "backend_error",
    status,
    code: detail.code,
    message: detail.message,
    requestId: detail.requestId,
  };
}

/** Fixed, user-safe message -- never pass raw caught-exception text here (may contain URLs, headers, or other sensitive detail). */
const NETWORK_ERROR_MESSAGE = "Network request failed.";

export function networkError(): NetworkApiError {
  return { type: "network_error", message: NETWORK_ERROR_MESSAGE };
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
