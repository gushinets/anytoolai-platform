import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AcceptanceBuilderResultView } from "../src/products/acceptanceBuilder/AcceptanceBuilderResult";
import { ACCEPTANCE_BUILDER_MESSAGES } from "../src/products/acceptanceBuilder/messages";
import { composeCopyText, extractCheckResult, extractDraftResult } from "../src/products/acceptanceBuilder/parseAcceptanceBuilder";
import { WORDS } from "../src/products/acceptanceBuilder/presentation";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import { makeRender } from "./support/renderWithI18n";

const fixtures = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../../../tests/fixtures/brief_language_eval/canonical.json"), "utf8")) as Record<string, Record<string, unknown>>;
const render = makeRender(ACCEPTANCE_BUILDER_MESSAGES);
afterEach(() => { cleanup(); window.localStorage.clear(); });

for (const [language, expected] of [["RU", "В брифе указаны все три списка."], ["ES", "El encargo especifica las tres listas."], ["EN", "The brief states all three lists."]] as const) {
  for (const mode of ["D", "C"] as const) {
    it(`${language} ${mode}: English UI copies analysis-language prose and ignores untrusted recap`, async () => {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
      const output = structuredClone(fixtures[`ANY761-AB-${mode}-${language}-basic`]!);
      output.document = { summary: "UNTRUSTED false verdict", sections: [{ title: "wrong", content: "All lists are missing. UNTRUSTED" }] };
      const result = mode === "C" ? extractCheckResult(output) : extractDraftResult(output);
      expect(result).not.toBeNull();
      const onCopy = vi.fn<(text: string) => Promise<boolean>>().mockResolvedValue(true);
      render(<AcceptanceBuilderResultView result={result!} onCopy={onCopy} />);
      fireEvent.click(screen.getByText("Structured recap"));
      fireEvent.click(screen.getByRole("button", { name: "Copy" }));
      await waitFor(() => expect(onCopy).toHaveBeenCalledWith(composeCopyText(result!)));
      const copy = onCopy.mock.calls[0]![0];
      expect(copy).toContain(expected);
      expect(copy).toContain('Ready to ship');
      expect(copy).not.toContain("UNTRUSTED");
      expect(screen.queryByText(/UNTRUSTED/)).toBeNull();
      if (language !== "EN") {
        expect(copy).not.toContain("The brief states");
        expect(copy).not.toContain("Verdict: does not meet expectations");
        expect(copy).not.toContain("the client should confirm");
      }
      if (mode === "C") expect(copy).toContain(language === "RU" ? "Вердикт: не соответствует ожиданиям." : language === "ES" ? "Veredicto: no cumple las expectativas." : "Verdict: does not meet expectations.");
    });
  }
  it(`${language}: missing lists and recap derive solely from missing_fields`, () => {
    const output = structuredClone(fixtures[`ANY761-AB-D-${language}-weak`]!);
    output.document = { summary: "All lists provided", sections: [] };
    const result = extractDraftResult(output)!;
    const copy = composeCopyText(result);
    expect(result.document.summary).not.toContain("All lists provided");
    expect(copy).toContain(WORDS[language.toLowerCase()]!.missing);
    expect(copy).toContain(WORDS[language.toLowerCase()]!.confirm);
    expect(copy).not.toContain(expected);
  });
}

it("uses the declared analysis override and regional tag, independently of UI", () => {
  const output = structuredClone(fixtures["ANY761-AB-C-RU-basic"]!) as { extracted: { values: { analysis_language: string } } };
  output.extracted.values.analysis_language = "es-MX";
  const result = extractCheckResult(output)!;
  expect(composeCopyText(result)).toContain("Veredicto: no cumple las expectativas.");
});

it("preserves unknown-language prose without English fallback sentences", () => {
  const output = { extracted: { values: { analysis_language: "ja", deliverables: ["報告書"] }, missing_fields: ["acceptance_criteria", "assumptions"] } };
  const result = extractDraftResult(output)!;
  expect(composeCopyText(result)).toContain("報告書");
  expect(composeCopyText(result)).not.toContain("Not specified in the brief");
  expect(composeCopyText(result)).not.toContain("the client should confirm");
});

it.each([undefined, "", "RU", 42])("rejects missing or invalid analysis language: %s", (language) => {
  const output = structuredClone(fixtures["ANY761-AB-D-RU-basic"]!) as { extracted: { values: Record<string, unknown> } };
  output.extracted.values.analysis_language = language;
  expect(extractDraftResult(output)).toBeNull();
});

it("rejects contradictory structured verdict/status and missing-list partitions", () => {
  const output = structuredClone(fixtures["ANY761-AB-C-RU-basic"]!) as { comparison: { verdict: string }; extracted: { missing_fields: string[] } };
  output.comparison.verdict = "meets_expectations";
  expect(extractCheckResult(output)).toBeNull();
  output.comparison.verdict = "does_not_meet";
  output.extracted.missing_fields = ["deliverables"];
  expect(extractCheckResult(output)).toBeNull();
});

for (const [language, sentences] of [
  ["RU", ["соответствует ожиданиям", "частично соответствует ожиданиям", "не соответствует ожиданиям"]],
  ["ES", ["cumple las expectativas", "cumple parcialmente las expectativas", "no cumple las expectativas"]],
] as const) {
  for (const [verdict, firstStatus, index] of [
    ["meets_expectations", "match", 0],
    ["partially_meets", "partial", 1],
    ["does_not_meet", "mismatch", 2],
  ] as const) {
    it(`${language}: recap and Copy bind ${verdict} to the structured decision`, () => {
      const output = structuredClone(fixtures[`ANY761-AB-C-${language}-basic`]!) as {
        comparison: { verdict: string; rationale: string; deltas: { status: string }[] };
        document?: unknown;
      };
      output.comparison.verdict = verdict;
      output.comparison.rationale = language === "RU" ? "Проверено." : "Revisado.";
      output.comparison.deltas.forEach((delta, position) => { delta.status = position === 0 ? firstStatus : "match"; });
      output.document = { summary: "UNTRUSTED opposite verdict", sections: [] };
      const result = extractCheckResult(output)!;
      const expected = `${language === "RU" ? "Вердикт" : "Veredicto"}: ${sentences[index]}.`;
      expect(result.document.summary).toBe(expected);
      expect(composeCopyText(result)).toContain(expected);
      expect(composeCopyText(result)).not.toContain("UNTRUSTED");
    });
  }
}
