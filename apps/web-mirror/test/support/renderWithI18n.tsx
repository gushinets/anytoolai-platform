import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { LocaleProvider, LOCALES, type Locale, type ProductMessagesByLocale } from "../../src/i18n";
import type { MessageTree } from "../../src/i18n/messageTypes";

/** The same English tree for every locale: for tests of a product that has no translations of its
 * own (the test-only product) or none needed (host-only components). */
export function englishForAllLocales(en: MessageTree): ProductMessagesByLocale {
  return Object.fromEntries(LOCALES.map((locale: Locale) => [locale, en])) as ProductMessagesByLocale;
}

/** Drop-in for RTL's `render`, inside the same `LocaleProvider` the product page shell uses. The
 * locale resolves from jsdom's `navigator.languages` (English) unless a test stored a choice. */
export function makeRender(productMessages: ProductMessagesByLocale) {
  function wrapper({ children }: { children: ReactNode }) {
    return <LocaleProvider productMessages={productMessages}>{children}</LocaleProvider>;
  }
  return (ui: ReactElement) => render(ui, { wrapper });
}
