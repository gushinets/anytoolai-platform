const JSON_CONTENT_TYPE = "application/json";

export function buildHeaders(
  defaultHeaders: Record<string, string>,
  overrideHeaders: Record<string, string> | undefined,
  requestId: string | undefined,
  hasBody: boolean,
): Headers {
  const headers = new Headers(defaultHeaders);
  for (const [key, value] of Object.entries(overrideHeaders ?? {})) {
    headers.set(key, value);
  }
  headers.set("Accept", JSON_CONTENT_TYPE);
  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", JSON_CONTENT_TYPE);
  }
  if (requestId && !headers.has("X-Request-ID")) {
    headers.set("X-Request-ID", requestId);
  }
  return headers;
}
