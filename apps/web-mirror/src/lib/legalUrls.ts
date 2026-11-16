/** Build-time URL; missing or invalid configuration hides only the policy link. */
export function privacyPolicyUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL?.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}
