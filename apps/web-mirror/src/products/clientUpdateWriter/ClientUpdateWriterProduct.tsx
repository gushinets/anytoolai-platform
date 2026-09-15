"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ResultView } from "../../components/ResultView";
import { ProductRunPage } from "../runtime/ProductRunPage";
import type { ProductDefinition, ProductFieldsProps, ProductResultProps, ProductRunEvent } from "../runtime/productDefinition";

const PRODUCT_ID = "client_update_writer";

const TONE_OPTIONS = ["neutral", "warm", "firm"] as const;
type Tone = (typeof TONE_OPTIONS)[number];

// Mirrors every mode's own `^\S([\s\S]*\S)?(?!\n)$` schema pattern (no leading/trailing
// whitespace) structurally, the same way ProposalAIProduct's own validate() does, instead of
// transcribing the regex itself. Backend validation stays authoritative either way.
function requiredTrimmedFieldError(value: string, label: string, maxLength: number): string | undefined {
  if (value.trim().length === 0) {
    return `${label} is required.`;
  }
  if (value !== value.trim()) {
    return `${label} must not start or end with whitespace.`;
  }
  if (value.length > maxLength) {
    return `${label} must be ${maxLength} characters or fewer.`;
  }
  return undefined;
}

function optionalTrimmedFieldError(value: string, label: string, maxLength: number): string | undefined {
  return value.length === 0 ? undefined : requiredTrimmedFieldError(value, label, maxLength);
}

function toneError(tone: Tone | ""): string | undefined {
  return tone ? undefined : "Tone is required.";
}

function ToneField({
  value,
  error,
  disabled,
  onChange,
}: {
  value: Tone | "";
  error?: string;
  disabled: boolean;
  onChange: (tone: Tone | "") => void;
}) {
  return (
    <>
      <label htmlFor="client-update-writer-tone">Tone</label>
      <select
        id="client-update-writer-tone"
        value={value}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value as Tone | "")}
        disabled={disabled}
        aria-invalid={Boolean(error)}
      >
        <option value="">Select a tone</option>
        {TONE_OPTIONS.map((tone) => (
          <option key={tone} value={tone}>
            {tone}
          </option>
        ))}
      </select>
      {error ? <p role="alert">{error}</p> : null}
    </>
  );
}

/**
 * All three modes produce `kernel.schemas.compose_reply_output_v1` (`renderer_contract.yaml`):
 * `text` verbatim, plus an optional `call_to_action`. There is no per-mode renderer variation.
 */
type ClientUpdateWriterResult = { text: string; callToAction?: string };

function extractComposeReplyResult(output: Record<string, unknown>): ClientUpdateWriterResult | null {
  if (typeof output.text !== "string") {
    return null;
  }
  return {
    text: output.text,
    callToAction: typeof output.call_to_action === "string" ? output.call_to_action : undefined,
  };
}

/** `renderer_contract.yaml`'s `call_to_action_composition: append_after_blank_line` -- `text`
 * alone when `call_to_action` is absent, otherwise `text` then one blank line then
 * `call_to_action`. Both the displayed and the copied text are this same composed string. */
function composeCopyText(result: ClientUpdateWriterResult): string {
  return result.callToAction ? `${result.text}\n\n${result.callToAction}` : result.text;
}

function ClientUpdateWriterResultView({ result, onCopy }: ProductResultProps<ClientUpdateWriterResult>) {
  return <ResultView text={composeCopyText(result)} onCopy={onCopy} />;
}

// ---- Update mode: progress_notes + tone -> client_update_writer.update_input_v1 ----

type UpdateValues = { progressNotes: string; tone: Tone | "" };

function validateUpdate(values: UpdateValues): Partial<Record<keyof UpdateValues, string>> {
  const errors: Partial<Record<keyof UpdateValues, string>> = {};
  const progressNotesError = requiredTrimmedFieldError(values.progressNotes, "Progress notes", 4000);
  if (progressNotesError) errors.progressNotes = progressNotesError;
  const tone = toneError(values.tone);
  if (tone) errors.tone = tone;
  return errors;
}

function UpdateFields({ values, errors, disabled, onChange }: ProductFieldsProps<UpdateValues>) {
  return (
    <>
      <label htmlFor="client-update-writer-progress-notes">Progress notes</label>
      <textarea
        id="client-update-writer-progress-notes"
        value={values.progressNotes}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("progressNotes", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.progressNotes)}
      />
      {errors.progressNotes ? <p role="alert">{errors.progressNotes}</p> : null}
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const updateDefinition: ProductDefinition<UpdateValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.update_v1",
  title: "Client Update Writer",
  emptyValues: { progressNotes: "", tone: "" },
  validate: validateUpdate,
  toInput: (values) => ({ progress_notes: values.progressNotes, tone: values.tone }),
  extractResult: extractComposeReplyResult,
  Fields: UpdateFields,
  Result: ClientUpdateWriterResultView,
  copy: {
    submit: "Write update",
    running: "Writing your update…",
    runFailed: "Something went wrong writing your update. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} updates remaining.`,
  },
};

// ---- Reply Draft mode: client_message + reply_goal + tone -> ...reply_draft_input_v1 ----

type ReplyDraftValues = { clientMessage: string; replyGoal: string; tone: Tone | "" };

function validateReplyDraft(values: ReplyDraftValues): Partial<Record<keyof ReplyDraftValues, string>> {
  const errors: Partial<Record<keyof ReplyDraftValues, string>> = {};
  const clientMessageError = requiredTrimmedFieldError(values.clientMessage, "Client message", 4000);
  if (clientMessageError) errors.clientMessage = clientMessageError;
  const replyGoalError = requiredTrimmedFieldError(values.replyGoal, "Reply goal", 4000);
  if (replyGoalError) errors.replyGoal = replyGoalError;
  const tone = toneError(values.tone);
  if (tone) errors.tone = tone;
  return errors;
}

function ReplyDraftFields({ values, errors, disabled, onChange }: ProductFieldsProps<ReplyDraftValues>) {
  return (
    <>
      <label htmlFor="client-update-writer-client-message">Client message</label>
      <textarea
        id="client-update-writer-client-message"
        value={values.clientMessage}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("clientMessage", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.clientMessage)}
      />
      {errors.clientMessage ? <p role="alert">{errors.clientMessage}</p> : null}

      <label htmlFor="client-update-writer-reply-goal">Reply goal</label>
      <textarea
        id="client-update-writer-reply-goal"
        value={values.replyGoal}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("replyGoal", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.replyGoal)}
      />
      {errors.replyGoal ? <p role="alert">{errors.replyGoal}</p> : null}
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const replyDraftDefinition: ProductDefinition<ReplyDraftValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.reply_draft_v1",
  title: "Client Update Writer",
  emptyValues: { clientMessage: "", replyGoal: "", tone: "" },
  validate: validateReplyDraft,
  toInput: (values) => ({ client_message: values.clientMessage, reply_goal: values.replyGoal, tone: values.tone }),
  extractResult: extractComposeReplyResult,
  Fields: ReplyDraftFields,
  Result: ClientUpdateWriterResultView,
  copy: {
    submit: "Write reply",
    running: "Writing your reply…",
    runFailed: "Something went wrong writing your reply. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} reply drafts remaining.`,
  },
};

// ---- Prepaid Request mode: billing_context{notes,amount,due_date?} + tone -> ...prepaid_request_input_v1 ----

type PrepaidRequestValues = { billingNotes: string; billingAmount: string; billingDueDate: string; tone: Tone | "" };

function validatePrepaidRequest(values: PrepaidRequestValues): Partial<Record<keyof PrepaidRequestValues, string>> {
  const errors: Partial<Record<keyof PrepaidRequestValues, string>> = {};
  const notesError = requiredTrimmedFieldError(values.billingNotes, "Billing notes", 4000);
  if (notesError) errors.billingNotes = notesError;
  const amountError = requiredTrimmedFieldError(values.billingAmount, "Amount", 200);
  if (amountError) errors.billingAmount = amountError;
  const dueDateError = optionalTrimmedFieldError(values.billingDueDate, "Due date", 200);
  if (dueDateError) errors.billingDueDate = dueDateError;
  const tone = toneError(values.tone);
  if (tone) errors.tone = tone;
  return errors;
}

function PrepaidRequestFields({ values, errors, disabled, onChange }: ProductFieldsProps<PrepaidRequestValues>) {
  return (
    <>
      <label htmlFor="client-update-writer-billing-notes">Billing notes</label>
      <textarea
        id="client-update-writer-billing-notes"
        value={values.billingNotes}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("billingNotes", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingNotes)}
      />
      {errors.billingNotes ? <p role="alert">{errors.billingNotes}</p> : null}

      <label htmlFor="client-update-writer-billing-amount">Amount</label>
      <input
        id="client-update-writer-billing-amount"
        value={values.billingAmount}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("billingAmount", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingAmount)}
      />
      {errors.billingAmount ? <p role="alert">{errors.billingAmount}</p> : null}

      <label htmlFor="client-update-writer-billing-due-date">Due date (optional)</label>
      <input
        id="client-update-writer-billing-due-date"
        value={values.billingDueDate}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("billingDueDate", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingDueDate)}
      />
      {errors.billingDueDate ? <p role="alert">{errors.billingDueDate}</p> : null}
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const prepaidRequestDefinition: ProductDefinition<PrepaidRequestValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.prepaid_request_v1",
  title: "Client Update Writer",
  emptyValues: { billingNotes: "", billingAmount: "", billingDueDate: "", tone: "" },
  validate: validatePrepaidRequest,
  toInput: (values) => ({
    billing_context: {
      notes: values.billingNotes,
      amount: values.billingAmount,
      ...(values.billingDueDate.trim() ? { due_date: values.billingDueDate } : {}),
    },
    tone: values.tone,
  }),
  extractResult: extractComposeReplyResult,
  Fields: PrepaidRequestFields,
  Result: ClientUpdateWriterResultView,
  copy: {
    submit: "Write request",
    running: "Writing your request…",
    runFailed: "Something went wrong writing your request. Please try again.",
    quotaRemaining: (remaining, limit) => `${remaining} of ${limit} prepaid requests remaining.`,
  },
};

// ---- Mode switcher: product-owned composition, not a shared-runtime concept (ANY-453's
// ProductDefinition/ProductRunPage contract already covers "one definition -> one scenario" for a
// single mount; each mode here is its own complete ProductDefinition, and switching between them
// is just which one this component currently renders). `key={modeId}` forces a full ProductRunPage
// remount on switch, so a mode change always starts from a clean form/run state, exactly like
// navigating to a different product would. ----

type ModeId = "update" | "reply_draft" | "prepaid_request";

const MODES: ReadonlyArray<{ id: ModeId; label: string }> = [
  { id: "update", label: "Update" },
  { id: "reply_draft", label: "Reply Draft" },
  { id: "prepaid_request", label: "Prepaid Request" },
];

export type ClientUpdateWriterProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
};

export function ClientUpdateWriterProduct({ client, onEvent }: ClientUpdateWriterProductProps) {
  const [modeId, setModeId] = useState<ModeId>("update");

  return (
    <>
      <fieldset>
        <legend>Mode</legend>
        {MODES.map(({ id, label }) => (
          <label key={id}>
            <input
              type="radio"
              name="client-update-writer-mode"
              value={id}
              checked={id === modeId}
              onChange={() => setModeId(id)}
            />
            {label}
          </label>
        ))}
      </fieldset>
      {modeId === "update" ? (
        <ProductRunPage key="update" definition={updateDefinition} client={client} onEvent={onEvent} />
      ) : modeId === "reply_draft" ? (
        <ProductRunPage key="reply_draft" definition={replyDraftDefinition} client={client} onEvent={onEvent} />
      ) : (
        <ProductRunPage key="prepaid_request" definition={prepaidRequestDefinition} client={client} onEvent={onEvent} />
      )}
    </>
  );
}
