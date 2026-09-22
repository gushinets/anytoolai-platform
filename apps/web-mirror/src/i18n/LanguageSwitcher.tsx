"use client";

import type { ChangeEvent } from "react";
import { Select } from "@anytoolai/shared-ui";
import { useHostT, useLocale } from "./LocaleProvider";
import { LOCALE_NAMES, LOCALES, isLocale } from "./locales";

/** The one language selector; rendered by `ProductPageShell` so no product implements its own. */
export function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();
  const t = useHostT();
  return (
    <div className="page-container">
      <label htmlFor="ui-language">{t("language.label")}</label>
      <Select
        id="ui-language"
        value={locale}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => {
          if (isLocale(event.target.value)) {
            setLocale(event.target.value);
          }
        }}
      >
        {LOCALES.map((code) => (
          <option key={code} value={code} lang={code}>
            {LOCALE_NAMES[code]}
          </option>
        ))}
      </Select>
    </div>
  );
}
