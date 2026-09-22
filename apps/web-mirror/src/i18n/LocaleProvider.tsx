"use client";

import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { IntlProvider, useTranslations } from "use-intl";
import { DEFAULT_LOCALE, type Locale } from "./locales";
import { acceptStoredLocaleFromEvent, LOCALE_STORAGE_KEY, readStoredLocale, writeStoredLocale } from "./localeStorage";
import { HOST_MESSAGES } from "./messages";
import { mergeMessages, type MessageTree } from "./messageTypes";
import { resolveLocale } from "./resolveLocale";

/** Every locale of the current product's own messages (its registry entry supplies these). */
export type ProductMessagesByLocale = Record<Locale, MessageTree>;

type LocaleContextValue = { locale: Locale; setLocale: (locale: Locale) => void };
const LocaleContext = createContext<LocaleContextValue | null>(null);

// SSR has no DOM: `useLayoutEffect` only upgrades to pre-paint timing in a browser (same pattern as
// `ProductRunPage`).
const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

// Fails loudly in tests / dev; in production a missing key is logged and the key path is shown
// rather than crashing the page.
function onError(error: Error): void {
  if (process.env.NODE_ENV !== "production") {
    throw error;
  }
  console.error(error);
}

/**
 * Host-owned locale state for one product page. Server and first client render use English; the
 * layout effect then applies the stored/browser locale before first paint. The tree below is never
 * remounted on a locale change (no `key={locale}`), so form values and run state survive a switch.
 */
export function LocaleProvider({
  productMessages,
  children,
}: {
  productMessages: ProductMessagesByLocale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useIsomorphicLayoutEffect(() => {
    setLocaleState(resolveLocale({ stored: readStoredLocale(), browserLanguages: navigator.languages }));
  }, []);
  // Code review finding (round 4): a passive `useEffect` left a one-paint lag between the switch
  // itself and `<html lang>` catching up, and never restored the value it overwrote -- App Router
  // does not remount a shared layout on client-side navigation, so leaving `/products/{id}` for an
  // out-of-scope English page (this provider is only mounted on product routes) could leave
  // `<html lang="ru">` over English content. `useIsomorphicLayoutEffect` (already used above for
  // resolution) removes the lag; capturing and restoring whatever was on `<html lang>` right before
  // this effect's own write -- not a hardcoded "en" -- correctly chains back to the root layout's
  // real value through any number of in-between switches, same as any effect that must leave a
  // shared, externally-owned value exactly as it found it.
  useIsomorphicLayoutEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = locale;
    return () => {
      document.documentElement.lang = previous;
    };
  }, [locale]);
  // Code review finding: with no `storage` listener, an explicit switch in one tab left every other
  // open tab of the same origin showing its old locale until its next reload/remount. `storage`
  // fires only in OTHER documents of the same origin, never the tab that made the write, so this
  // can't loop with `setLocale` below. `event.newValue === null` covers the key being cleared
  // (e.g. site data reset), which re-resolves down to the browser language / English.
  //
  // Code review finding (round 3): updating only this component's React state left
  // `localeStorage.ts`'s own memory (`lastKnownLocale`/`isStale`) untouched -- a tab whose own last
  // write had failed kept distrusting the primary (per `readStoredLocale`'s contract) even after
  // this event proved another tab's write to the same key had just succeeded, so a later remount in
  // THIS tab silently reverted to its own stale value instead of what the UI had just switched to.
  // `acceptStoredLocaleFromEvent` folds the event's (authoritative -- `storage` only ever fires for
  // a write/removal that actually took effect) value into that memory too, before it can be lost.
  useEffect(() => {
    function onStorage(event: StorageEvent) {
      // Code review finding (round 5): `storage` also fires for `sessionStorage` (a same-origin
      // iframe sharing this top-level browsing context can dispatch one for its OWN, unrelated
      // `sessionStorage`), so a bare key match isn't enough -- `storageArea` identifies which
      // Storage object actually changed. `readStoredLocale`/`writeStoredLocale` only ever touch
      // `window.localStorage`, so that's the only area this listener may react to.
      if (event.storageArea !== window.localStorage) {
        return;
      }
      if (event.key === LOCALE_STORAGE_KEY || event.key === null) {
        acceptStoredLocaleFromEvent(event.newValue);
        setLocaleState(resolveLocale({ stored: event.newValue, browserLanguages: navigator.languages }));
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const messages = useMemo(
    // English underneath every locale: a key missing from a locale falls back to English.
    () => ({
      host: mergeMessages(HOST_MESSAGES[DEFAULT_LOCALE], HOST_MESSAGES[locale]),
      product: mergeMessages(productMessages[DEFAULT_LOCALE], productMessages[locale]),
    }),
    [locale, productMessages],
  );
  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale: (next) => {
        writeStoredLocale(next);
        setLocaleState(next);
      },
    }),
    [locale],
  );

  return (
    <LocaleContext.Provider value={value}>
      <IntlProvider locale={locale} messages={messages} onError={onError}>
        {children}
      </IntlProvider>
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useLocale must be used inside <LocaleProvider>.");
  }
  return value;
}

/** The app-owned translate function: products and the shared runtime depend on this shape, not on
 * `use-intl`. Keys are dotted paths inside the namespace. */
export type Translate = (key: string, values?: Record<string, string | number>) => string;

/** Generic runtime/result/error/validation messages owned by the shared host -- never product
 * meaning (e.g. `tone` labels are product-owned, spread from `products/shared/toneMessages/` into
 * each product's own `product` namespace instead). */
export function useHostT(): Translate {
  return useTranslations("host");
}

/** The current product's own messages (field labels, mode names, submit/running/failure copy). */
export function useProductT(): Translate {
  return useTranslations("product");
}
