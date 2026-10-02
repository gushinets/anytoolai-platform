/** `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` (set at build time; unset means every registered product
 * is enabled). One parse, cached per raw value, shared by the registry and the handoff button. */
let cached: { raw: string | undefined; ids: ReadonlySet<string> | null } | null = null;

export function enabledProductIds(): ReadonlySet<string> | null {
  const raw = process.env.NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS;
  if (cached?.raw !== raw || cached === null) {
    cached = { raw, ids: raw === undefined ? null : new Set(raw.split(",").map((id) => id.trim()).filter(Boolean)) };
  }
  return cached.ids;
}

export function isProductEnabled(productId: string): boolean {
  return enabledProductIds()?.has(productId) ?? true;
}
