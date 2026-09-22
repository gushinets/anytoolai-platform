"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { TextArea } from "@anytoolai/shared-ui";
import { ResultView } from "../../components/ResultView";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, requiredTrimmedFieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";

const TONE_OPTIONS = [
  { value: "warm", label: "Warm & personable" },
  { value: "neutral", label: "Clear & professional" },
  { value: "firm", label: "Confident & direct" },
] as const;
type Tone = (typeof TONE_OPTIONS)[number]["value"];

export type ProposalAIValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone;
};

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, string>> {
  return collectFieldErrors<ProposalAIValues>([
    ["taskText", requiredTrimmedFieldError(values.taskText, "Task description", 4000)],
    ["freelancerPositioning", requiredTrimmedFieldError(values.freelancerPositioning, "Your positioning", 4000)],
  ]);
}

function ProposalAIFields({ values, errors, disabled, onChange }: ProductFieldsProps<ProposalAIValues>) {
  return (
    <>
      <label htmlFor="proposal-ai-task-text">Describe the task</label>
      <TextArea
        id="proposal-ai-task-text"
        value={values.taskText}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.taskText)}
      />
      {errors.taskText ? <p role="alert">{errors.taskText}</p> : null}

      <label htmlFor="proposal-ai-positioning">Your positioning</label>
      <TextArea
        id="proposal-ai-positioning"
        value={values.freelancerPositioning}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.freelancerPositioning)}
      />
      {errors.freelancerPositioning ? <p role="alert">{errors.freelancerPositioning}</p> : null}

      <fieldset role="radiogroup">
        <legend>Proposal style</legend>
        {TONE_OPTIONS.map((option) => (
          <label key={option.value} htmlFor={`proposal-ai-tone-${option.value}`}>
            <input
              id={`proposal-ai-tone-${option.value}`}
              type="radio"
              name="proposal-ai-tone"
              value={option.value}
              checked={values.tone === option.value}
              onChange={() => onChange("tone", option.value)}
              disabled={disabled}
            />
            {option.label}
          </label>
        ))}
      </fieldset>
    </>
  );
}

/**
 * ProposalAI's product meaning, and nothing else: its fields and their validation, the mapping to
 * `proposal_ai.generate_input_v1`, the canonical field `renderer_contract.yaml` pins (`text` --
 * angle/rationale/model/provider are excluded on purpose and never reach the renderer), the
 * `copy_result` activation, and its copy. Everything else is the shared `ProductRunPage`.
 */
export const proposalAiDefinition: ProductDefinition<ProposalAIValues, string> = {
  productId: "proposal_ai",
  scenarioId: "proposal_ai.generate_v1",
  title: "ProposalAI",
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
  copy: {
    submit: "Generate proposal",
    running: "Generating your proposal…",
    runFailed: "Something went wrong generating your proposal. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} proposals remaining.`,
  },
};

export type ProposalAIProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function ProposalAIProduct({ client, onEvent, visitId }: ProposalAIProductProps) {
  return <ProductRunPage definition={proposalAiDefinition} client={client} onEvent={onEvent} visitId={visitId} />;
}
