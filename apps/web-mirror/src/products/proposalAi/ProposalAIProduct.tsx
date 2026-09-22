"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { TextArea as CanonicalTextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, requiredTrimmedFieldError, type FieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import styles from "./ProposalAIProduct.module.css";

// ANY-521's own product-owned tone UI (three visible radio choices, not the shared `ToneSelect`
// dropdown -- its exec-plan explicitly rules out "a speculative shared RadioGroup abstraction for
// one product"). Values stay the untranslated wire enum; labels come from `toneOptions.<value>`.
const TONE_VALUES = ["warm", "neutral", "firm"] as const;
type Tone = (typeof TONE_VALUES)[number];

export type ProposalAIValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone;
};

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, FieldError>> {
  return collectFieldErrors<ProposalAIValues>([
    ["taskText", requiredTrimmedFieldError(values.taskText, 4000)],
    ["freelancerPositioning", requiredTrimmedFieldError(values.freelancerPositioning, 4000)],
  ]);
}

function ProposalAIFields({ values, errors, disabled, onChange }: ProductFieldsProps<ProposalAIValues>) {
  const t = useProductT();
  return (
    <>
      <div className={styles.fieldGroup}>
        <label htmlFor="proposal-ai-task-text">{t("fields.taskText")}</label>
        <CanonicalTextArea
          id="proposal-ai-task-text"
          className={styles.taskTextArea}
          value={values.taskText}
          placeholder={t("fields.taskTextPlaceholder")}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
          disabled={disabled}
          aria-invalid={Boolean(errors.taskText)}
          aria-describedby={`proposal-ai-task-help${errors.taskText ? " proposal-ai-task-error" : ""}`}
        />
        <p id="proposal-ai-task-help" className={styles.help}>
          {t("fields.taskTextHelp")}
        </p>
        <FieldErrorMessage
          id="proposal-ai-task-error"
          className={styles.error}
          error={errors.taskText}
          label={t("fieldNames.taskText")}
        />
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="proposal-ai-positioning">{t("fields.freelancerPositioning")}</label>
        <CanonicalTextArea
          id="proposal-ai-positioning"
          className={styles.positioningTextArea}
          value={values.freelancerPositioning}
          placeholder={t("fields.freelancerPositioningPlaceholder")}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
          disabled={disabled}
          aria-invalid={Boolean(errors.freelancerPositioning)}
          aria-describedby={`proposal-ai-positioning-help${errors.freelancerPositioning ? " proposal-ai-positioning-error" : ""}`}
        />
        <p id="proposal-ai-positioning-help" className={styles.help}>
          {t("fields.freelancerPositioningHelp")}
        </p>
        <FieldErrorMessage
          id="proposal-ai-positioning-error"
          className={styles.error}
          error={errors.freelancerPositioning}
          label={t("fieldNames.freelancerPositioning")}
        />
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
 * `proposal_ai.generate_input_v1`, the canonical field `renderer_contract.yaml` pins (`text` --
 * angle/rationale/model/provider are excluded on purpose and never reach the renderer), the
 * `copy_result` activation, and its message scope (the copy itself is in `messages/`). Everything
 * else is the shared `ProductRunPage`.
 */
export const proposalAiDefinition: ProductDefinition<ProposalAIValues, string> = {
  productId: "proposal_ai",
  scenarioId: "proposal_ai.generate_v1",
  messageScope: "generate",
  hasDescription: true,
  hasStartAnother: true,
  emptyValues: { taskText: "", freelancerPositioning: "", tone: "warm" },
  validate,
  toInput: (values) => ({
    task_text: values.taskText,
    freelancer_positioning: values.freelancerPositioning,
    tone: values.tone,
  }),
  extractResult: (output) => (typeof output.text === "string" ? output.text : null),
  Fields: ProposalAIFields,
  Result: ({ result, onCopy }) => <ResultView text={result} onCopy={onCopy} />,
};

export type ProposalAIProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function ProposalAIProduct({ client, onEvent, visitId }: ProposalAIProductProps) {
  return <ProductRunPage definition={proposalAiDefinition} client={client} onEvent={onEvent} visitId={visitId} />;
}
