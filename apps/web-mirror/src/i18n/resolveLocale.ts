import { DEFAULT_LOCALE, isLocale, type Locale } from "./locales";

/** `de-AT` / `pt_BR` / `EN-us` -> `de` / `pt` / `en`; `undefined` when the base language is unsupported. */
function toSupportedLocale(tag: string): Locale | undefined {
  const base = tag.split(/[-_]/)[0]?.toLowerCase() ?? "";
  return isLocale(base) ? base : undefined;
}

/**
 * Deterministic UI locale: explicit persisted choice, then the first supported browser language
 * (in the browser's own preference order), then English.
 */
export function resolveLocale({
  stored,
  browserLanguages,
}: {
  stored: string | null;
  browserLanguages: readonly string[];
}): Locale {
  if (stored !== null && isLocale(stored)) {
    return stored;
  }
  for (const tag of browserLanguages) {
    const locale = toSupportedLocale(tag);
    if (locale) {
      return locale;
    }
  }
  return DEFAULT_LOCALE;
}
