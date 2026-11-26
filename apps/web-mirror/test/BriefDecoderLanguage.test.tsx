import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BriefDecoderProduct } from "../src/products/briefDecoder/BriefDecoderProduct";
import { BriefDecoderResultView } from "../src/products/briefDecoder/BriefDecoderResult";
import { BRIEF_DECODER_MESSAGES } from "../src/products/briefDecoder/messages";
import { extractBriefDecoderResult } from "../src/products/briefDecoder/parseBriefDecoder";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import { LOCALES } from "../src/i18n";
import {
  guestIdentityResponse, makeClient, quotaResponse, resultResponse, routesFor,
  runtimeConfigResponse, sessionResponse, startResponse,
} from "./fixtures/platformResponses";
import { makeRender } from "./support/renderWithI18n";

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

it("updates a visible missing-task hint in every locale while keeping the Russian draft", async () => {
  const ids = { productId: "brief_decoder", scenarioId: "brief_decoder.decode_v1" } as const;
  const routes = routesFor(ids);
  const { client, calls } = makeClient({
    [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
    [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
    [routes.QUOTA]: [quotaResponse(ids)],
    [routes.START]: [startResponse()],
    [routes.SESSION]: [sessionResponse()],
    [routes.RESULT]: [resultResponse(ids, {
      output: {
        ...fixtures["ANY761-BD-RU-borscht"],
        issues: [{ category: "missing_task_description", severity: "high", description: "Нет задачи клиента." }],
      },
    })],
  });
  const brief = "Рецепт борща: свёкла, капуста, говядина. Варить два часа.";
  render(<BriefDecoderProduct client={client} />);
  const field = await screen.findByLabelText<HTMLTextAreaElement>("Client brief");
  const switcher = screen.getByRole("combobox", { name: "Language" });
  fireEvent.change(field, { target: { value: brief } });
  fireEvent.click(screen.getByRole("button", { name: "Decode brief" }));
  await screen.findByText(BRIEF_DECODER_MESSAGES.en.validation.missing_task_description);

  const translations = new Set<string>();
  for (const locale of LOCALES) {
    fireEvent.change(switcher, { target: { value: locale } });
    const message = BRIEF_DECODER_MESSAGES[locale].validation.missing_task_description;
    translations.add(message);
    const hint = await screen.findByText(message);
    expect(hint.getAttribute("role")).toBe("alert");
    expect(field.getAttribute("aria-describedby")?.split(" ")).toContain(hint.id);
    expect(field.value).toBe(brief);
  }
  expect(translations.size).toBe(LOCALES.length);
  expect(calls.filter((call) => call.key === routes.START)).toHaveLength(1);
});
