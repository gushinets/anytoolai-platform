// Host i18n infrastructure: locale resolution, fallback merge, and translation-resource completeness
// for the host and for every registered product (so a newly registered product is covered without
// editing this file).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { createTranslator } from "use-intl";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LOCALES, LOCALE_NAMES, isLocale, type Locale } from "../src/i18n";
import {
  acceptStoredLocaleFromEvent,
  LOCALE_STORAGE_KEY,
  readStoredLocale,
  resetUnpersistedLocaleForTests,
  writeStoredLocale,
} from "../src/i18n/localeStorage";
import { HOME_MESSAGES } from "../src/app/homeMessages";
import { HANDOFF_MESSAGES } from "../src/components/handoffMessages";
import { HOST_MESSAGES } from "../src/i18n/messages";
import { mergeMessages, type MessageTree } from "../src/i18n/messageTypes";
import { resolveLocale } from "../src/i18n/resolveLocale";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { listRegisteredProducts } from "../src/products/registry";

describe("readStoredLocale / writeStoredLocale (staleness on a failed write)", () => {
  afterEach(() => {
    window.localStorage.clear();
    resetUnpersistedLocaleForTests();
    vi.restoreAllMocks();
  });

  it("keeps the newer explicit choice, not the older stored one, when setItem fails", () => {
    // The exact regression from code review: storage already holds an explicit choice, so
    // getItem() keeps succeeding with a non-null (but now stale) value -- a naive `getItem() ??
    // memory` fallback is never consulted in that case.
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    writeStoredLocale("fr");

    expect(readStoredLocale()).toBe("fr");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
  });

  it("trusts storage again once a later write succeeds", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new Error("blocked");
    });
    writeStoredLocale("fr");
    expect(readStoredLocale()).toBe("fr");

    writeStoredLocale("de");

    expect(readStoredLocale()).toBe("de");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("de");
  });

  it("does not resurrect an earlier write once the key is genuinely removed", () => {
    // Code review finding (round 2): a successful write followed by the key actually being cleared
    // (e.g. site data reset, or code elsewhere in this document calling removeItem) must read back
    // null -- not the earlier "fr", which would wrongly skip browser-language resolution.
    writeStoredLocale("fr");
    expect(readStoredLocale()).toBe("fr");

    window.localStorage.removeItem(LOCALE_STORAGE_KEY);

    expect(readStoredLocale()).toBeNull();
  });

  it("acceptStoredLocaleFromEvent adopts a confirmed external value even while stale from a failed local write", () => {
    // Code review finding (round 3): a `storage` event only ever fires for a write/removal that
    // actually took effect elsewhere, so it is authoritative for this key regardless of whatever
    // made THIS tab's own memory stale -- readStoredLocale() must stop returning the old,
    // now-superseded local value once that confirmation arrives. Real storage is updated too (a
    // real `storage` event always reflects the one physical store this tab's own later getItem()
    // reads from), same as the fix itself: memory alone, without a matching real value, would be
    // overwritten by the very next non-stale read.
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new Error("blocked");
    });
    writeStoredLocale("fr");
    expect(readStoredLocale()).toBe("fr");

    window.localStorage.setItem(LOCALE_STORAGE_KEY, "de");
    acceptStoredLocaleFromEvent("de");

    expect(readStoredLocale()).toBe("de");
  });

  it("acceptStoredLocaleFromEvent(null) adopts a cross-tab clear the same way", () => {
    writeStoredLocale("fr");

    window.localStorage.removeItem(LOCALE_STORAGE_KEY);
    acceptStoredLocaleFromEvent(null);

    expect(readStoredLocale()).toBeNull();
  });
});

describe("resolveLocale", () => {
  it("prefers an explicit stored choice over the browser languages", () => {
    expect(resolveLocale({ stored: "ru", browserLanguages: ["de-DE"] })).toBe("ru");
  });

  it("uses the first supported browser language, in the browser's own order", () => {
    expect(resolveLocale({ stored: null, browserLanguages: ["ja-JP", "it-IT", "de"] })).toBe("it");
  });

  it.each([
    ["en-US", "en"],
    ["en-GB", "en"],
    ["de-AT", "de"],
    ["de-DE", "de"],
    ["fr-CA", "fr"],
    ["es-MX", "es"],
    ["pt-BR", "pt"],
    ["pt-PT", "pt"],
    ["ru-RU", "ru"],
    ["PT_br", "pt"],
  ])("maps the regional browser locale %s to the base locale %s", (tag, expected) => {
    expect(resolveLocale({ stored: null, browserLanguages: [tag] })).toBe(expected);
  });

  it("falls back to English for unsupported or missing browser languages", () => {
    expect(resolveLocale({ stored: null, browserLanguages: ["ja-JP", "zh-CN"] })).toBe("en");
    expect(resolveLocale({ stored: null, browserLanguages: [] })).toBe("en");
  });

  it("ignores a stored value that is not a supported locale", () => {
    expect(resolveLocale({ stored: "klingon", browserLanguages: ["fr"] })).toBe("fr");
    expect(resolveLocale({ stored: "toString", browserLanguages: [] })).toBe("en");
  });
});

describe("isLocale", () => {
  it("accepts exactly the seven supported locales and rejects inherited object keys", () => {
    expect([...LOCALES]).toEqual(["en", "fr", "it", "de", "es", "ru", "pt"]);
    expect(isLocale("pt")).toBe(true);
    expect(isLocale("pt-BR")).toBe(false);
    expect(isLocale("constructor")).toBe(false);
  });
});

describe("mergeMessages (English fallback)", () => {
  it("fills a key missing from the locale with the English one, at any depth", () => {
    const en = { a: "A", nested: { b: "B", c: "C" } };
    expect(mergeMessages(en, { nested: { c: "C!" } })).toEqual({ a: "A", nested: { b: "B", c: "C!" } });
  });
});

type Bundle = { name: string; byLocale: Record<Locale, MessageTree>; namespace: string };

function bundles(): Bundle[] {
  return [
    { name: "host", byLocale: HOST_MESSAGES, namespace: "host" },
    { name: "home", byLocale: HOME_MESSAGES, namespace: "product" },
    { name: "handoff", byLocale: HANDOFF_MESSAGES, namespace: "product" },
    ...listRegisteredProducts().map((product) => ({
      name: product.productId,
      byLocale: product.messages,
      namespace: "product",
    })),
  ];
}

function flatten(tree: MessageTree, prefix = ""): Map<string, string> {
  const flat = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") {
      flat.set(path, value);
    } else {
      for (const [nestedPath, nested] of flatten(value, path)) {
        flat.set(nestedPath, nested);
      }
    }
  }
  return flat;
}

// `{name}` / `{name, plural, ...}` arguments, ignoring the `{...}` bodies of plural branches
// (`one {# character}`), which are text, not arguments.
function placeholders(message: string): string[] {
  const names = [...message.matchAll(/(?<!\b(?:zero|one|two|few|many|other|=\d+)\s*)\{\s*(\w+)\s*[,}]/g)].map(
    (match) => match[1] as string,
  );
  return [...new Set(names)].sort();
}

describe("translation resources", () => {
  it("cover every registered product and the host in every supported locale", () => {
    expect(listRegisteredProducts().map((product) => product.productId)).toEqual(
      expect.arrayContaining(["proposal_ai", "client_update_writer"]),
    );
    for (const bundle of bundles()) {
      expect(Object.keys(bundle.byLocale).sort(), bundle.name).toEqual([...LOCALES].sort());
    }
  });

  it("have the same keys as English in every locale (no missing, no extra)", () => {
    for (const bundle of bundles()) {
      const englishKeys = [...flatten(bundle.byLocale.en).keys()].sort();
      for (const locale of LOCALES) {
        expect([...flatten(bundle.byLocale[locale]).keys()].sort(), `${bundle.name}/${locale}`).toEqual(englishKeys);
      }
    }
  });

  it("provide a nonempty title for every registered product in every locale", () => {
    for (const product of listRegisteredProducts()) {
      for (const locale of LOCALES) {
        expect(product.messages[locale].title.trim(), `${product.productId}/${locale}/title`).not.toBe("");
      }
    }
  });

  it("keep every ICU placeholder of the English message, and leave none empty", () => {
    for (const bundle of bundles()) {
      const english = flatten(bundle.byLocale.en);
      for (const locale of LOCALES) {
        for (const [key, message] of flatten(bundle.byLocale[locale])) {
          expect(message.trim(), `${bundle.name}/${locale}/${key}`).not.toBe("");
          expect(placeholders(message), `${bundle.name}/${locale}/${key}`).toEqual(placeholders(english.get(key) ?? ""));
        }
      }
    }
  });

  it("format without an ICU syntax error in every locale (e.g. a stray apostrophe before a placeholder)", () => {
    const args = { product: "Product", field: "Field", remaining: 2, limit: 5, maxLength: 3 };
    for (const bundle of bundles()) {
      for (const locale of LOCALES) {
        const messages = { [bundle.namespace]: bundle.byLocale[locale] };
        const translate = createTranslator({
          locale,
          messages,
          namespace: bundle.namespace,
          onError: (error) => {
            throw error;
          },
        });
        const format = translate as unknown as (key: string, values: typeof args) => string;
        for (const key of flatten(bundle.byLocale[locale]).keys()) {
          expect(() => format(key, args), `${bundle.name}/${locale}/${key}`).not.toThrow();
        }
      }
    }
  });

  it("do not leave a locale identical to English wholesale (a copy-pasted, untranslated file)", () => {
    for (const bundle of bundles()) {
      const english = flatten(bundle.byLocale.en);
      for (const locale of LOCALES.filter((candidate) => candidate !== "en")) {
        const translated = flatten(bundle.byLocale[locale]);
        const same = [...translated].filter(([key, message]) => message === english.get(key)).length;
        expect(same / translated.size, `${bundle.name}/${locale}`).toBeLessThan(0.5);
      }
    }
  });

  it("pluralize the max-length validation per locale (Russian has distinct one/few/many forms)", () => {
    const format = (locale: Locale, maxLength: number) =>
      createTranslator({ locale, messages: { host: HOST_MESSAGES[locale] }, namespace: "host" })(
        "validation.maxLength",
        { field: "F", maxLength },
      );
    expect(format("en", 1)).toBe("F: 1 character maximum.");
    expect(format("en", 5)).toBe("F: 5 characters maximum.");
    expect(new Set([1, 2, 5].map((count) => format("ru", count))).size).toBe(3);
  });

  it("uses natural Russian word forms in the Proposal AI quota", () => {
    const translate = createTranslator({ locale: "ru", messages: { product: PROPOSAL_AI_MESSAGES.ru }, namespace: "product" });
    expect(translate("quotaRemaining", { remaining: 1, limit: 10 })).toBe("Осталось 1 предложение из 10.");
    expect(translate("quotaRemaining", { remaining: 2, limit: 10 })).toBe("Осталось 2 предложения из 10.");
    expect(translate("quotaRemaining", { remaining: 5, limit: 10 })).toBe("Осталось 5 предложений из 10.");
  });

  it("show each locale under its own untranslated name in the selector", () => {
    expect(LOCALE_NAMES).toEqual({
      en: "English",
      fr: "Français",
      it: "Italiano",
      de: "Deutsch",
      es: "Español",
      ru: "Русский",
      pt: "Português",
    });
  });
});

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    return statSync(path).isDirectory() ? sourceFiles(path) : /\.(ts|tsx)$/.test(entry) ? [path] : [];
  });
}

describe("i18n boundaries", () => {
  const SRC = join(__dirname, "..", "src");

  it("imports use-intl only from src/i18n", () => {
    const offenders = sourceFiles(SRC).filter(
      (file) => !file.startsWith(join(SRC, "i18n")) && /from ["']use-intl/.test(readFileSync(file, "utf8")),
    );
    expect(offenders).toEqual([]);
  });

  it("keeps shared-ui and ce-kit localization-agnostic (neither imports the host i18n layer)", () => {
    const packages = join(__dirname, "..", "..", "..", "packages", "frontend");
    const offenders = ["shared-ui", "ce-kit"].flatMap((name) =>
      sourceFiles(join(packages, name, "src")).filter((file) =>
        /from ["'][^"']*(web-mirror|use-intl|\/i18n)/.test(readFileSync(file, "utf8")),
      ),
    );
    expect(offenders).toEqual([]);
  });
});
