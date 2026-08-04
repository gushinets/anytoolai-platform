export function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim();
  if (trimmed.length === 0) {
    throw new Error("PlatformApiClient requires a non-empty baseUrl.");
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export function joinUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}
