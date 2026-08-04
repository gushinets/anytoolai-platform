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
