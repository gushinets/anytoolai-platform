import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BriefDecoderResultView } from "../src/products/briefDecoder/BriefDecoderResult";
import { BRIEF_DECODER_MESSAGES } from "../src/products/briefDecoder/messages";
import { extractBriefDecoderResult } from "../src/products/briefDecoder/parseBriefDecoder";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import { makeRender } from "./support/renderWithI18n";
import { LOCALES } from "../src/i18n";
import { LanguageSwitcher } from "../src/i18n/LanguageSwitcher";

const fixtures = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../../../tests/fixtures/brief_language_eval/canonical.json"), "utf8")) as Record<string, Record<string, unknown>>;
const render = makeRender(BRIEF_DECODER_MESSAGES);
afterEach(() => { cleanup(); window.localStorage.clear(); });

for (const [locale, copyLabel] of [["ru", "Скопировать"], ["en", "Copy"], ["es", "Copiar"]] as const) {
  it(`Russian recipe: ${locale} UI copies the structured result verbatim`, async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    const result = extractBriefDecoderResult(fixtures["ANY761-BD-RU-borscht"]!);
    expect(result).not.toBeNull();
    const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
    render(<BriefDecoderResultView result={result!} onCopy={onCopy} />);
    fireEvent.click(screen.getByRole("button", { name: copyLabel }));
    await waitFor(() => expect(onCopy).toHaveBeenCalledTimes(1));
    const copy = onCopy.mock.calls[0]![0];
    for (const value of Object.values(result!.brief.values)) {
      for (const item of Array.isArray(value) ? value : [value]) expect(copy).toContain(item);
    }
    for (const question of result!.questions) expect(copy).toContain(question.question);
    expect(copy).not.toContain(result!.document.summary);
    expect(copy.startsWith(`${BRIEF_DECODER_MESSAGES[locale].result.brief}\n`)).toBe(true);
  });
}

it.each(LOCALES)("copies Russian questions unchanged with %s action labels", async (locale) => {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  const result = extractBriefDecoderResult(fixtures["ANY761-BD-RU-borscht"]!)!;
  const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
  const labels = BRIEF_DECODER_MESSAGES[locale].copy;
  render(<BriefDecoderResultView result={result} onCopy={onCopy} />);
  fireEvent.click(screen.getByRole("button", { name: labels.questions }));
  expect(await screen.findByRole("button", { name: labels.questionsCopied })).toBeTruthy();
  expect(onCopy).toHaveBeenCalledExactlyOnceWith(result.questions.map(({ question }) => question).join("\n"));
});

it("keeps the authored questions unchanged when the UI locale is switched", async () => {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
  const result = extractBriefDecoderResult(fixtures["ANY761-BD-RU-borscht"]!)!;
  const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
  render(<><LanguageSwitcher /><BriefDecoderResultView result={result} onCopy={onCopy} /></>);
  fireEvent.click(screen.getByRole("button", { name: "Copy questions" }));
  await screen.findByRole("button", { name: "Questions copied" });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "ru" } });
  fireEvent.click(await screen.findByRole("button", { name: "Вопросы скопированы" }));
  await screen.findByRole("button", { name: "Вопросы скопированы" });
  const expected = result.questions.map(({ question }) => question).join("\n");
  expect(onCopy.mock.calls).toEqual([[expected], [expected]]);
});
