"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { Select, TextArea as CanonicalTextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { ResultView } from "../../components/ResultView";
import { LOCALES, LOCALE_NAMES, useProductT, type Locale } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import {
  collectFieldErrors,
  requiredBackendTrimmedFieldError,
  trimBackendWhitespace,
  type FieldError,
} from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductResultProps, ProductRunEvent } from "../runtime/productDefinition";
import styles from "./ProposalAIProduct.module.css";

// Product-owned tone UI with three visible radio choices. Values stay the untranslated wire
// enum; ProposalAI's descriptive labels come from its own `toneOptions.<value>` messages.
const TONE_VALUES = ["warm", "neutral", "firm"] as const;
type Tone = (typeof TONE_VALUES)[number];

// Mirrors `proposal_ai.generate_input_v1` maxLength for both text fields.
const TEXT_MAX_LENGTH = 4000;
// The counter appears only when the limit is near, so it stays quiet for ordinary input.
const COUNTER_THRESHOLD = 3500;

// "auto" = the language of the task (nothing is sent); any other value is a locale code the
// backend takes as `language`. It is the language of the proposal, not of the interface.
const AUTO_LANGUAGE = "auto";
type ProposalLanguage = typeof AUTO_LANGUAGE | Locale;

export type ProposalAIValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone;
  language: ProposalLanguage;
};

// Mirrors `proposal_ai.generate_output_v1`: the proposal and the `experience_gap` issues.
export type ProposalAIGap = { description: string };
export type ProposalAIResult = { text: string; gaps: ProposalAIGap[] };

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, FieldError>> {
  return collectFieldErrors<ProposalAIValues>([
    ["taskText", requiredBackendTrimmedFieldError(values.taskText, TEXT_MAX_LENGTH)],
    ["freelancerPositioning", requiredBackendTrimmedFieldError(values.freelancerPositioning, TEXT_MAX_LENGTH)],
  ]);
}

function isGap(value: unknown): value is ProposalAIGap {
  return typeof value === "object" && value !== null && "description" in value && typeof value.description === "string";
}

function extractResult(output: Record<string, unknown>): ProposalAIResult | null {
  if (typeof output.text !== "string") {
    return null;
  }
  const gaps = Array.isArray(output.gaps) ? output.gaps.filter(isGap).map(({ description }) => ({ description })) : [];
  return { text: output.text, gaps };
}

function ProposalAIResultView({ result, onCopy, secondaryAction }: ProductResultProps<ProposalAIResult>) {
  const t = useProductT();
  return (
    <div className={styles.result}>
      <ResultView text={result.text} onCopy={onCopy} secondaryAction={secondaryAction} embedded />
      {result.gaps.length > 0 ? (
        <section className={styles.gaps} aria-labelledby="proposal-ai-gaps-heading">
          <h3 id="proposal-ai-gaps-heading" className={styles.gapsTitle}>
            {t("result.gapsTitle")}
          </h3>
          <p className={styles.help}>{t("result.gapsHint")}</p>
          <ul className={styles.gapsList}>
            {result.gaps.map((gap, index) => (
              <li key={index}>{gap.description}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function RequiredLabel({ htmlFor, children }: { htmlFor: string; children: string }) {
  const t = useProductT();
  return (
    <label htmlFor={htmlFor}>
      {children} <span className={styles.required}>({t("fields.required")})</span>
    </label>
  );
}

/** "N / 4000", announced politely, shown only near the limit. The live region itself is always in
 * the DOM so screen readers pick up the text when it appears. There is deliberately no hard
 * `maxLength` on the textarea: it would cut a pasted text silently, while the counter and the
 * validation error tell the user what to shorten. */
function Counter({ length }: { length: number }) {
  return (
    <span className={length > TEXT_MAX_LENGTH ? `${styles.counter} ${styles.counterOver}` : styles.counter} aria-live="polite">
      {length > COUNTER_THRESHOLD ? `${length} / ${TEXT_MAX_LENGTH}` : ""}
    </span>
  );
}

function ProposalAIFields({ values, errors, disabled, onChange }: ProductFieldsProps<ProposalAIValues>) {
  const t = useProductT();
  return (
    <>
      <div className={styles.fieldGroup}>
        <RequiredLabel htmlFor="proposal-ai-task-text">{t("fields.taskText")}</RequiredLabel>
        <CanonicalTextArea
          id="proposal-ai-task-text"
          className={styles.taskTextArea}
          value={values.taskText}
          placeholder={t("fields.taskTextPlaceholder")}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
          disabled={disabled}
          aria-required="true"
          aria-invalid={Boolean(errors.taskText)}
          aria-describedby={`proposal-ai-task-help${errors.taskText ? " proposal-ai-task-error" : ""}`}
        />
        <div className={styles.helpRow}>
          <p id="proposal-ai-task-help" className={styles.help}>
            {t("fields.taskTextHelp")}
          </p>
          <Counter length={values.taskText.length} />
        </div>
        <FieldErrorMessage
          id="proposal-ai-task-error"
          className={styles.error}
          error={errors.taskText}
          label={t("fieldNames.taskText")}
        />
      </div>

      <div className={styles.fieldGroup}>
        <RequiredLabel htmlFor="proposal-ai-positioning">{t("fields.freelancerPositioning")}</RequiredLabel>
        <CanonicalTextArea
          id="proposal-ai-positioning"
          className={styles.positioningTextArea}
          value={values.freelancerPositioning}
          placeholder={t("fields.freelancerPositioningPlaceholder")}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
          disabled={disabled}
          aria-required="true"
          aria-invalid={Boolean(errors.freelancerPositioning)}
          aria-describedby={`proposal-ai-positioning-help${errors.freelancerPositioning ? " proposal-ai-positioning-error" : ""}`}
        />
        <div className={styles.helpRow}>
          <p id="proposal-ai-positioning-help" className={styles.help}>
            {t("fields.freelancerPositioningHelp")}
          </p>
          <Counter length={values.freelancerPositioning.length} />
        </div>
        <FieldErrorMessage
          id="proposal-ai-positioning-error"
          className={styles.error}
          error={errors.freelancerPositioning}
          label={t("fieldNames.freelancerPositioning")}
        />
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="proposal-ai-language">{t("fields.languageLabel")}</label>
        <Select
          id="proposal-ai-language"
          value={values.language}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange("language", event.target.value as ProposalLanguage)}
          disabled={disabled}
          aria-describedby="proposal-ai-language-help"
        >
          <option value={AUTO_LANGUAGE}>{t("fields.languageAuto")}</option>
          {LOCALES.map((code) => (
            <option key={code} value={code}>
              {LOCALE_NAMES[code]}
            </option>
          ))}
        </Select>
        <p id="proposal-ai-language-help" className={styles.help}>
          {t("fields.languageHelp")}
        </p>
      </div>

      <fieldset className={styles.toneGroup} role="radiogroup">
        <legend className={styles.legend}>{t("fields.toneLegend")}</legend>
        <div className={styles.toneOptions}>
          {TONE_VALUES.map((value) => (
            <label className={styles.toneOption} key={value} htmlFor={`proposal-ai-tone-${value}`}>
              <input
                className={styles.radio}
                id={`proposal-ai-tone-${value}`}
                type="radio"
                name="proposal-ai-tone"
                value={value}
                checked={values.tone === value}
                onChange={() => onChange("tone", value)}
                disabled={disabled}
              />
              {t(`toneOptions.${value}`)}
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}

/**
 * ProposalAI's product meaning, and nothing else: its fields and their validation, the mapping to
 * `proposal_ai.generate_input_v1`, the parts `renderer_contract.yaml` pins (`text` is the only copy target, `gaps`
 * is informational; angle/rationale/model/provider never reach the renderer), the
 * `copy_result` activation, and its message scope (the copy itself is in `messages/`). Everything
 * else is the shared `ProductRunPage`.
 */
export const proposalAiDefinition: ProductDefinition<ProposalAIValues, ProposalAIResult> = {
  productId: "proposal_ai",
  scenarioId: "proposal_ai.generate_v1",
  messageScope: "generate",
  hasDescription: true,
  emptyValues: { taskText: "", freelancerPositioning: "", tone: "warm", language: AUTO_LANGUAGE },
  validate,
  toInput: (values) => ({
    task_text: trimBackendWhitespace(values.taskText),
    freelancer_positioning: trimBackendWhitespace(values.freelancerPositioning),
    tone: values.tone,
    // Sent only when chosen: without it the backend writes in the language of the task.
    ...(values.language === AUTO_LANGUAGE ? {} : { language: values.language }),
  }),
  extractResult,
  Fields: ProposalAIFields,
  Result: ProposalAIResultView,
};

export type ProposalAIProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function ProposalAIProduct({ client, onEvent, visitId }: ProposalAIProductProps) {
  return <ProductRunPage definition={proposalAiDefinition} client={client} onEvent={onEvent} visitId={visitId} />;
}
