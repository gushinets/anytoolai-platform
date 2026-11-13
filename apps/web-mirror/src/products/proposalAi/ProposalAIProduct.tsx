"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import type { AttachProps } from "../runtime/attachSession";
import { Select, TextArea as CanonicalTextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { ResultView } from "../../components/ResultView";
import { LOCALES, LOCALE_NAMES, useProductT, type Locale } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { isOneOf, isRecord } from "../shared/resultGuards";
import {
  backendTrimmedLength,
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

const EMPTY_VALUES: ProposalAIValues = { taskText: "", freelancerPositioning: "", tone: "warm", language: AUTO_LANGUAGE };

function isTone(value: unknown): value is Tone {
  return typeof value === "string" && (TONE_VALUES as readonly string[]).includes(value);
}

function isProposalLanguage(value: unknown): value is ProposalLanguage {
  return value === AUTO_LANGUAGE || (typeof value === "string" && (LOCALES as readonly string[]).includes(value));
}

function parseDraftValues(raw: unknown): ProposalAIValues | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  const value = raw as Record<string, unknown>;
  return {
    taskText: typeof value.taskText === "string" ? value.taskText : EMPTY_VALUES.taskText,
    freelancerPositioning: typeof value.freelancerPositioning === "string" ? value.freelancerPositioning : EMPTY_VALUES.freelancerPositioning,
    tone: isTone(value.tone) ? value.tone : EMPTY_VALUES.tone,
    language: isProposalLanguage(value.language) ? value.language : EMPTY_VALUES.language,
  };
}

// Mirrors `proposal_ai.generate_output_v1`: the proposal and the `experience_gap` issues.
export type ProposalAIGap = { description: string };
export type ProposalAIResult = {
  text: string;
  gaps: ProposalAIGap[];
  fieldErrors?: Partial<Record<keyof ProposalAIValues, FieldError>>;
};

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, FieldError>> {
  return collectFieldErrors<ProposalAIValues>([
    ["taskText", requiredBackendTrimmedFieldError(values.taskText, TEXT_MAX_LENGTH)],
    ["freelancerPositioning", requiredBackendTrimmedFieldError(values.freelancerPositioning, TEXT_MAX_LENGTH)],
  ]);
}

function normalizeValues(values: ProposalAIValues): ProposalAIValues {
  return {
    ...values,
    taskText: trimBackendWhitespace(values.taskText),
    freelancerPositioning: trimBackendWhitespace(values.freelancerPositioning),
  };
}

const GAP_FIELDS = {
  experience_gap: null,
  missing_task_description: "taskText",
  missing_profile_information: "freelancerPositioning",
} as const;

function isGapCategory(value: unknown): value is keyof typeof GAP_FIELDS {
  return typeof value === "string" && Object.hasOwn(GAP_FIELDS, value);
}

function extractResult(output: Record<string, unknown>): ProposalAIResult | null {
  if (typeof output.text !== "string" || !output.text.trim()) {
    return null;
  }
  // Old text-only results remain readable; present issue lists must obey the closed contract.
  const issues = output.gaps === undefined ? [] : output.gaps;
  if (!Array.isArray(issues)) return null;
  const gaps: ProposalAIGap[] = [];
  const fieldErrors: Partial<Record<keyof ProposalAIValues, FieldError>> = {};
  for (const issue of issues) {
    if (!isRecord(issue) || !isGapCategory(issue.category) ||
      typeof issue.description !== "string" || !issue.description.trim() ||
      !isOneOf(["low", "medium", "high"] as const, issue.severity)) return null;
    const field = GAP_FIELDS[issue.category];
    if (field === null) gaps.push({ description: issue.description });
    else fieldErrors[field] = { code: "product", key: `validation.${issue.category}` };
  }
  return Object.keys(fieldErrors).length > 0
    ? { text: output.text, gaps, fieldErrors }
    : { text: output.text, gaps };
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

/** "N / 4000" next to the help text once the limit is near, counted like the backend and the
 * validation do (code points of the trimmed text). The visible number is not a live region, it would
 * be read out on every keystroke; a visually hidden status announces only when the state changes
 * (near, over). There is deliberately no hard `maxLength` on the textarea: it would cut a pasted
 * text silently, while the counter and the validation error tell the user what to shorten. */
function Counter({ value }: { value: string }) {
  const t = useProductT();
  const length = backendTrimmedLength(value);
  const state = length > TEXT_MAX_LENGTH ? "over" : length > COUNTER_THRESHOLD ? "near" : "ok";
  return (
    <>
      <span className={state === "over" ? `${styles.counter} ${styles.counterOver}` : styles.counter} aria-hidden="true">
        {state === "ok" ? "" : `${length} / ${TEXT_MAX_LENGTH}`}
      </span>
      <span className={styles.srOnly} aria-live="polite">
        {state === "ok" ? "" : t(state === "over" ? "fields.counterOver" : "fields.counterNear", { max: TEXT_MAX_LENGTH })}
      </span>
    </>
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
          <Counter value={values.taskText} />
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
          <Counter value={values.freelancerPositioning} />
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
  emptyValues: EMPTY_VALUES,
  draft: { parseValues: parseDraftValues },
  validate,
  normalizeValues,
  toInput: (values) => {
    const normalized = normalizeValues(values);
    return {
      task_text: normalized.taskText,
      freelancer_positioning: normalized.freelancerPositioning,
      tone: normalized.tone,
      // Sent only when chosen: without it the backend writes in the language of the task.
      ...(normalized.language === AUTO_LANGUAGE ? {} : { language: normalized.language }),
    };
  },
  extractResult,
  resultFieldErrors: (result) => result.fieldErrors ?? {},
  Fields: ProposalAIFields,
  Result: ProposalAIResultView,
};

export type ProposalAIProductProps = AttachProps & {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function ProposalAIProduct({ client, onEvent, visitId, ...attach }: ProposalAIProductProps) {
  return <ProductRunPage definition={proposalAiDefinition} client={client} onEvent={onEvent} visitId={visitId} {...attach} />;
}
