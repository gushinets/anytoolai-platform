"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { Input, TextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, requiredTrimmedFieldError, type FieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import { ToneSelect, type Tone } from "../shared/tone";

export type ProposalAIValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone | "";
  language: string;
};

// Mirrors generate_input.schema.json's `language` pattern -- checked structurally below instead
// of transcribing that schema's equivalent (but harder to read) regex. Backend validation stays
// authoritative either way.
const LANGUAGE_PATTERN = /^[a-z]{2}(-[A-Z]{2})?$/;

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, FieldError>> {
  return collectFieldErrors<ProposalAIValues>([
    ["taskText", requiredTrimmedFieldError(values.taskText, 4000)],
    ["freelancerPositioning", requiredTrimmedFieldError(values.freelancerPositioning, 4000)],
    [
      "language",
      values.language && !LANGUAGE_PATTERN.test(values.language)
        ? { code: "product", key: "validation.languageFormat" }
        : undefined,
    ],
  ]);
}

function ProposalAIFields({ values, errors, disabled, onChange }: ProductFieldsProps<ProposalAIValues>) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="proposal-ai-task-text">{t("fields.taskText")}</label>
      <TextArea
        id="proposal-ai-task-text"
        value={values.taskText}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.taskText)}
      />
      <FieldErrorMessage error={errors.taskText} label={t("fieldNames.taskText")} />

      <label htmlFor="proposal-ai-positioning">{t("fields.freelancerPositioning")}</label>
      <TextArea
        id="proposal-ai-positioning"
        value={values.freelancerPositioning}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.freelancerPositioning)}
      />
      <FieldErrorMessage error={errors.freelancerPositioning} label={t("fieldNames.freelancerPositioning")} />

      <label htmlFor="proposal-ai-tone">{t("fields.tone")}</label>
      <ToneSelect
        id="proposal-ai-tone"
        value={values.tone}
        onChange={(tone) => onChange("tone", tone)}
        disabled={disabled}
        placeholderLabel={t("fields.tonePlaceholder")}
      />

      <label htmlFor="proposal-ai-language">{t("fields.language")}</label>
      <Input
        id="proposal-ai-language"
        value={values.language}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("language", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.language)}
      />
      <FieldErrorMessage error={errors.language} label={t("fieldNames.language")} />
    </>
  );
}

/**
 * ProposalAI's product meaning, and nothing else: its fields and their validation, the mapping to
 * `proposal_ai.generate_input_v1`, the canonical field `renderer_contract.yaml` pins (`text` --
 * angle/rationale/model/provider are excluded on purpose and never reach the renderer), the
 * `copy_result` activation, and its message scope (the copy itself is in `messages/`). Everything else is the shared `ProductRunPage`.
 */
export const proposalAiDefinition: ProductDefinition<ProposalAIValues, string> = {
  productId: "proposal_ai",
  scenarioId: "proposal_ai.generate_v1",
  messageScope: "generate",
  emptyValues: { taskText: "", freelancerPositioning: "", tone: "", language: "" },
  validate,
  toInput: (values) => ({
    task_text: values.taskText,
    freelancer_positioning: values.freelancerPositioning,
    ...(values.tone ? { tone: values.tone } : {}),
    ...(values.language ? { language: values.language } : {}),
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
