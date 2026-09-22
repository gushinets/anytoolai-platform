// The only surface the rest of the app imports; `use-intl` stays behind it.
export { LanguageSwitcher } from "./LanguageSwitcher";
export {
  LocaleProvider,
  useHostT,
  useLocale,
  useProductT,
  type ProductMessagesByLocale,
  type Translate,
} from "./LocaleProvider";
export { LOCALES, LOCALE_NAMES, isLocale, type Locale } from "./locales";
export type { Shape } from "./messageTypes";
