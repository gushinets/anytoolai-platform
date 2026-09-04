/** Fields the backend's `{ error: { code, message, request_id } }` envelope promises are safe. */
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

  const error = payload.error;
  if (typeof error !== "object" || error === null) {
    return null;
  }

  const { code, message, request_id: requestId } = error as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string" || typeof requestId !== "string") {
    return null;
  }

  return { code, message, requestId };
}
