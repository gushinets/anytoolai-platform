// Closed set of UI locales (docs/agent/coding-conventions.md "closed sets"): the `Record<Locale, ...>`
// maps below make a new locale a compile error everywhere it must be handled. Display names are
// endonyms and are never translated, so a user can always find their own language.
export const LOCALE_NAMES = {
  en: "English",
  fr: "Français",
  it: "Italiano",
  de: "Deutsch",
  es: "Español",
  ru: "Русский",
  pt: "Português",
} as const;

export type Locale = keyof typeof LOCALE_NAMES;
export const LOCALES = Object.keys(LOCALE_NAMES) as readonly Locale[];
export const DEFAULT_LOCALE: Locale = "en";

export function isLocale(value: string): value is Locale {
  return Object.hasOwn(LOCALE_NAMES, value);
}
