/** Any nested ICU message tree; what `use-intl` accepts as `messages`. */
export type MessageTree = { [key: string]: string | MessageTree };

/** Same key structure as `T`, every leaf a string: a non-English file typed `Shape<typeof en>`
 * fails typecheck on a missing or extra key. */
export type Shape<T> = T extends string ? string : { [K in keyof T]: Shape<T[K]> };

/** `overrides` on top of `base`, recursively: how a locale falls back to English key by key. */
export function mergeMessages(base: MessageTree, overrides: MessageTree): MessageTree {
  const merged: MessageTree = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const existing = merged[key];
    merged[key] =
      typeof value === "string" || typeof existing !== "object" ? value : mergeMessages(existing, value);
  }
  return merged;
}
