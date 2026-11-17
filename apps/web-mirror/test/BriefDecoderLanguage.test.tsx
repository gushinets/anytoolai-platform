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

const fixtures = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../../../tests/fixtures/brief_language_eval/canonical.json"), "utf8")) as Record<string, Record<string, unknown>>;
const render = makeRender(BRIEF_DECODER_MESSAGES);
afterEach(() => { cleanup(); window.localStorage.clear(); });

for (const [locale, copyLabel] of [["ru", "Скопировать"], ["en", "Copy"], ["es", "Copiar"]] as const) {
  it(`Russian recipe: ${locale} UI copies the entire reviewed document without rewriting it`, async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    const result = extractBriefDecoderResult(fixtures["ANY761-BD-RU-borscht"]!);
    expect(result).not.toBeNull();
    const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
    render(<BriefDecoderResultView result={result!} onCopy={onCopy} />);
    fireEvent.click(screen.getByRole("button", { name: copyLabel }));
    const { sections, summary } = result!.document;
    const expected = [...sections.map(section => `${section.title}\n${section.content}`), summary].join("\n\n");
    await waitFor(() => expect(onCopy).toHaveBeenCalledWith(expected));
    expect(onCopy).toHaveBeenCalledTimes(1);
  });
}
