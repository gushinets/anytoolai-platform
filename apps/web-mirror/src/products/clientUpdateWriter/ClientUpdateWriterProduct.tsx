"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ResultView } from "../../components/ResultView";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, optionalTrimmedFieldError, requiredTrimmedFieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductResultProps, ProductRunEvent } from "../runtime/productDefinition";
import { TONE_OPTIONS, type Tone } from "../runtime/tone";

const PRODUCT_ID = "client_update_writer";

// `quotas.yaml` declares `dimension: product` -- one 3-run pool shared by all three modes, not a
// separate pool per mode -- so every mode's `quotaRemaining` copy uses this same, mode-agnostic
// wording (code review finding: per-mode wording like "X of Y updates remaining" implied separate
// pools that don't exist).
const quotaRemainingCopy = (remaining: number, limit: number) =>
  `${remaining} of ${limit} Client Update Writer runs remaining.`;

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
  return collectFieldErrors<UpdateValues>([
    ["progressNotes", requiredTrimmedFieldError(values.progressNotes, "Progress notes", 4000)],
    ["tone", toneError(values.tone)],
  ]);
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
    quotaRemaining: quotaRemainingCopy,
  },
};

// ---- Reply Draft mode: client_message + reply_goal + tone -> ...reply_draft_input_v1 ----

type ReplyDraftValues = { clientMessage: string; replyGoal: string; tone: Tone | "" };

function validateReplyDraft(values: ReplyDraftValues): Partial<Record<keyof ReplyDraftValues, string>> {
  return collectFieldErrors<ReplyDraftValues>([
    ["clientMessage", requiredTrimmedFieldError(values.clientMessage, "Client message", 4000)],
    ["replyGoal", requiredTrimmedFieldError(values.replyGoal, "Reply goal", 4000)],
    ["tone", toneError(values.tone)],
  ]);
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
    quotaRemaining: quotaRemainingCopy,
  },
};

// ---- Prepaid Request mode: billing_context{notes,amount,due_date?} + tone -> ...prepaid_request_input_v1 ----

type PrepaidRequestValues = { billingNotes: string; billingAmount: string; billingDueDate: string; tone: Tone | "" };

function validatePrepaidRequest(values: PrepaidRequestValues): Partial<Record<keyof PrepaidRequestValues, string>> {
  return collectFieldErrors<PrepaidRequestValues>([
    ["billingNotes", requiredTrimmedFieldError(values.billingNotes, "Billing notes", 4000)],
    ["billingAmount", requiredTrimmedFieldError(values.billingAmount, "Amount", 200)],
    ["billingDueDate", optionalTrimmedFieldError(values.billingDueDate, "Due date", 200)],
    ["tone", toneError(values.tone)],
  ]);
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
    quotaRemaining: quotaRemainingCopy,
  },
};

// ---- Mode switcher: product-owned composition, not a shared-runtime concept (ANY-453's
// ProductDefinition/ProductRunPage contract already covers "one definition -> one scenario" for a
// single mount; each mode here is its own complete ProductDefinition, and switching between them
// is just which one this component currently renders). `key={modeId}` forces a full ProductRunPage
// remount on switch, so a mode change always starts from a clean form/run state, exactly like
// navigating to a different product would -- each mode's form values have an incompatible shape
// (UpdateValues/ReplyDraftValues/PrepaidRequestValues), so the remount is load-bearing, not just
// defensive: without it, ProductRunPage's own `values` state would keep the previous mode's shape. ----

type ModeId = "update" | "reply_draft" | "prepaid_request";

// One map, not a separate label list plus a separate mode -> definition ternary (code review
// finding: the two used to list the same three modes independently) -- `Record<ModeId, ...>`
// also makes a missing mode a compile error instead of needing a runtime exhaustiveness check.
// Each mode's own V is a distinct, incompatible values shape (see the docstring above); `any`
// here is the map's value type only, not a loosening of any individual mode's own
// ProductDefinition<V, R> declaration above.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyModeDefinition = ProductDefinition<any, ClientUpdateWriterResult>;

const MODE_CONFIG: Record<ModeId, { label: string; definition: AnyModeDefinition }> = {
  update: { label: "Update", definition: updateDefinition },
  reply_draft: { label: "Reply Draft", definition: replyDraftDefinition },
  prepaid_request: { label: "Prepaid Request", definition: prepaidRequestDefinition },
};
const MODE_IDS = Object.keys(MODE_CONFIG) as ModeId[];

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
        {MODE_IDS.map((id) => (
          <label key={id}>
            <input
              type="radio"
              name="client-update-writer-mode"
              value={id}
              checked={id === modeId}
              onChange={() => setModeId(id)}
            />
            {MODE_CONFIG[id].label}
          </label>
        ))}
      </fieldset>
      <ProductRunPage key={modeId} definition={MODE_CONFIG[modeId].definition} client={client} onEvent={onEvent} />
    </>
  );
}
