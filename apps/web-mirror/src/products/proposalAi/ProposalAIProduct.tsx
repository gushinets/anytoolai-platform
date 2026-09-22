"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { TextArea as CanonicalTextArea } from "@anytoolai/shared-ui";
import { ResultView } from "../../components/ResultView";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, requiredTrimmedFieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import styles from "./ProposalAIProduct.module.css";

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
      <div className={styles.fieldGroup}>
        <label htmlFor="proposal-ai-task-text">Describe the task</label>
        <CanonicalTextArea
          id="proposal-ai-task-text"
          className={styles.taskTextArea}
          value={values.taskText}
          placeholder="Paste the client's task, brief, or job post."
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("taskText", event.target.value)}
          disabled={disabled}
          aria-invalid={Boolean(errors.taskText)}
          aria-describedby={`proposal-ai-task-help${errors.taskText ? " proposal-ai-task-error" : ""}`}
        />
        <p id="proposal-ai-task-help" className={styles.help}>
          Include the goal, deliverables, constraints, and timeline when available.
        </p>
        {errors.taskText ? (
          <p id="proposal-ai-task-error" className={styles.error} role="alert">
            {errors.taskText}
          </p>
        ) : null}
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="proposal-ai-positioning">Your positioning</label>
        <CanonicalTextArea
          id="proposal-ai-positioning"
          className={styles.positioningTextArea}
          value={values.freelancerPositioning}
          placeholder="Describe the experience and strengths that make you a good fit."
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("freelancerPositioning", event.target.value)}
          disabled={disabled}
          aria-invalid={Boolean(errors.freelancerPositioning)}
          aria-describedby={`proposal-ai-positioning-help${errors.freelancerPositioning ? " proposal-ai-positioning-error" : ""}`}
        />
        <p id="proposal-ai-positioning-help" className={styles.help}>
          Use only claims you can stand behind—the proposal will not invent experience.
        </p>
        {errors.freelancerPositioning ? (
          <p id="proposal-ai-positioning-error" className={styles.error} role="alert">
            {errors.freelancerPositioning}
          </p>
        ) : null}
      </div>

      <fieldset className={styles.toneGroup} role="radiogroup">
        <legend className={styles.legend}>Proposal style</legend>
        <div className={styles.toneOptions}>
          {TONE_OPTIONS.map((option) => (
            <label className={styles.toneOption} key={option.value} htmlFor={`proposal-ai-tone-${option.value}`}>
              <input
                className={styles.radio}
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
        </div>
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
    description: "Turn a client brief and your relevant strengths into a proposal ready to send.",
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
