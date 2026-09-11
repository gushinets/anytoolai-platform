"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ResultView } from "../../components/ResultView";
import { ProductRunPage } from "../runtime/ProductRunPage";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";

const TONE_OPTIONS = ["neutral", "warm", "firm"] as const;
type Tone = (typeof TONE_OPTIONS)[number];

export type ProposalAIValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone | "";
  language: string;
};

// Mirrors generate_input.schema.json's `language` pattern; task_text/freelancer_positioning are
// checked structurally below instead of transcribing that schema's equivalent (but harder to
// read) regex. Backend validation stays authoritative either way.
const LANGUAGE_PATTERN = /^[a-z]{2}(-[A-Z]{2})?$/;

function validate(values: ProposalAIValues): Partial<Record<keyof ProposalAIValues, string>> {
  const errors: Partial<Record<keyof ProposalAIValues, string>> = {};
  for (const [field, label] of [
    ["taskText", "Task description"],
    ["freelancerPositioning", "Your positioning"],
  ] as const) {
    const value = values[field];
    if (value.trim().length === 0) {
      errors[field] = `${label} is required.`;
    } else if (value !== value.trim()) {
      errors[field] = `${label} must not start or end with whitespace.`;
    } else if (value.length > 4000) {
      errors[field] = `${label} must be 4000 characters or fewer.`;
    }
  }
  if (values.language && !LANGUAGE_PATTERN.test(values.language)) {
    errors.language = 'Language must look like "en" or "en-US".';
  }
  return errors;
}

function ProposalAIFields({ values, errors, disabled, onChange }: ProductFieldsProps<ProposalAIValues>) {
  return (
    <>
      <label htmlFor="proposal-ai-task-text">Describe the task</label>
      <textarea
        id="proposal-ai-task-text"
        value={values.taskText}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.taskText)}
      />
      {errors.taskText ? <p role="alert">{errors.taskText}</p> : null}

      <label htmlFor="proposal-ai-positioning">Your positioning</label>
      <textarea
        id="proposal-ai-positioning"
        value={values.freelancerPositioning}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.freelancerPositioning)}
      />
      {errors.freelancerPositioning ? <p role="alert">{errors.freelancerPositioning}</p> : null}

      <label htmlFor="proposal-ai-tone">Tone (optional)</label>
      <select
        id="proposal-ai-tone"
        value={values.tone}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange("tone", event.target.value as Tone | "")}
        disabled={disabled}
      >
        <option value="">Default</option>
        {TONE_OPTIONS.map((tone) => (
          <option key={tone} value={tone}>
            {tone}
          </option>
        ))}
      </select>

      <label htmlFor="proposal-ai-language">Language (optional)</label>
      <input
        id="proposal-ai-language"
        value={values.language}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("language", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.language)}
      />
      {errors.language ? <p role="alert">{errors.language}</p> : null}
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
  title: "ProposalAI",
  emptyValues: { taskText: "", freelancerPositioning: "", tone: "", language: "" },
  validate,
  toInput: (values) => ({
    task_text: values.taskText,
    freelancer_positioning: values.freelancerPositioning,
    ...(values.tone ? { tone: values.tone } : {}),
    ...(values.language ? { language: values.language } : {}),
  }),
  extractResult: (output) => (typeof output.text === "string" ? output.text : null),
  copyNextActionId: "copy_result",
  Fields: ProposalAIFields,
  Result: ({ result, onCopied }) => <ResultView text={result} onCopied={onCopied} />,
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
};

export function ProposalAIProduct({ client, onEvent }: ProposalAIProductProps) {
  return <ProductRunPage definition={proposalAiDefinition} client={client} onEvent={onEvent} />;
}
