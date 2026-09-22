"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { Input, TextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { ResultView } from "../../components/ResultView";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import {
  collectFieldErrors,
  optionalTrimmedFieldError,
  requiredTrimmedFieldError,
  type FieldError,
} from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductResultProps, ProductRunEvent } from "../runtime/productDefinition";
import { ToneSelect, type Tone } from "../shared/tone";

const PRODUCT_ID = "client_update_writer";

// Mirrors each mode's own input schema maxLength (schemas/*.json under
// products/client_update_writer/) -- named once instead of as bare literals repeated at every
// field's validate() call (code review finding).
const LONG_FIELD_MAX_LENGTH = 4000;
const SHORT_FIELD_MAX_LENGTH = 200;

function toneError(tone: Tone | ""): FieldError | undefined {
  return tone ? undefined : { code: "required" };
}

function ToneField({
  value,
  error,
  disabled,
  onChange,
}: {
  value: Tone | "";
  error?: FieldError;
  disabled: boolean;
  onChange: (tone: Tone | "") => void;
}) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="client-update-writer-tone">{t("fields.tone")}</label>
      <ToneSelect
        id="client-update-writer-tone"
        value={value}
        onChange={onChange}
        disabled={disabled}
        placeholderLabel={t("fields.tonePlaceholder")}
        ariaInvalid={Boolean(error)}
      />
      <FieldErrorMessage error={error} label={t("fieldNames.tone")} />
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

function validateUpdate(values: UpdateValues): Partial<Record<keyof UpdateValues, FieldError>> {
  return collectFieldErrors<UpdateValues>([
    ["progressNotes", requiredTrimmedFieldError(values.progressNotes, LONG_FIELD_MAX_LENGTH)],
    ["tone", toneError(values.tone)],
  ]);
}

function UpdateFields({ values, errors, disabled, onChange }: ProductFieldsProps<UpdateValues>) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="client-update-writer-progress-notes">{t("fields.progressNotes")}</label>
      <TextArea
        id="client-update-writer-progress-notes"
        value={values.progressNotes}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("progressNotes", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.progressNotes)}
      />
      <FieldErrorMessage error={errors.progressNotes} label={t("fieldNames.progressNotes")} />
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const updateDefinition: ProductDefinition<UpdateValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.update_v1",
  messageScope: "update",
  emptyValues: { progressNotes: "", tone: "" },
  validate: validateUpdate,
  toInput: (values) => ({ progress_notes: values.progressNotes, tone: values.tone }),
  extractResult: extractComposeReplyResult,
  Fields: UpdateFields,
  Result: ClientUpdateWriterResultView,
};

// ---- Reply Draft mode: client_message + reply_goal + tone -> ...reply_draft_input_v1 ----

type ReplyDraftValues = { clientMessage: string; replyGoal: string; tone: Tone | "" };

function validateReplyDraft(values: ReplyDraftValues): Partial<Record<keyof ReplyDraftValues, FieldError>> {
  return collectFieldErrors<ReplyDraftValues>([
    ["clientMessage", requiredTrimmedFieldError(values.clientMessage, LONG_FIELD_MAX_LENGTH)],
    ["replyGoal", requiredTrimmedFieldError(values.replyGoal, LONG_FIELD_MAX_LENGTH)],
    ["tone", toneError(values.tone)],
  ]);
}

function ReplyDraftFields({ values, errors, disabled, onChange }: ProductFieldsProps<ReplyDraftValues>) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="client-update-writer-client-message">{t("fields.clientMessage")}</label>
      <TextArea
        id="client-update-writer-client-message"
        value={values.clientMessage}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("clientMessage", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.clientMessage)}
      />
      <FieldErrorMessage error={errors.clientMessage} label={t("fieldNames.clientMessage")} />

      <label htmlFor="client-update-writer-reply-goal">{t("fields.replyGoal")}</label>
      <TextArea
        id="client-update-writer-reply-goal"
        value={values.replyGoal}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("replyGoal", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.replyGoal)}
      />
      <FieldErrorMessage error={errors.replyGoal} label={t("fieldNames.replyGoal")} />
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const replyDraftDefinition: ProductDefinition<ReplyDraftValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.reply_draft_v1",
  messageScope: "reply_draft",
  emptyValues: { clientMessage: "", replyGoal: "", tone: "" },
  validate: validateReplyDraft,
  toInput: (values) => ({ client_message: values.clientMessage, reply_goal: values.replyGoal, tone: values.tone }),
  extractResult: extractComposeReplyResult,
  Fields: ReplyDraftFields,
  Result: ClientUpdateWriterResultView,
};

// ---- Prepaid Request mode: billing_context{notes,amount,due_date?} + tone -> ...prepaid_request_input_v1 ----

type PrepaidRequestValues = { billingNotes: string; billingAmount: string; billingDueDate: string; tone: Tone | "" };

function validatePrepaidRequest(values: PrepaidRequestValues): Partial<Record<keyof PrepaidRequestValues, FieldError>> {
  return collectFieldErrors<PrepaidRequestValues>([
    ["billingNotes", requiredTrimmedFieldError(values.billingNotes, LONG_FIELD_MAX_LENGTH)],
    ["billingAmount", requiredTrimmedFieldError(values.billingAmount, SHORT_FIELD_MAX_LENGTH)],
    ["billingDueDate", optionalTrimmedFieldError(values.billingDueDate, SHORT_FIELD_MAX_LENGTH)],
    ["tone", toneError(values.tone)],
  ]);
}

function PrepaidRequestFields({ values, errors, disabled, onChange }: ProductFieldsProps<PrepaidRequestValues>) {
  const t = useProductT();
  return (
    <>
      <label htmlFor="client-update-writer-billing-notes">{t("fields.billingNotes")}</label>
      <TextArea
        id="client-update-writer-billing-notes"
        value={values.billingNotes}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("billingNotes", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingNotes)}
      />
      <FieldErrorMessage error={errors.billingNotes} label={t("fieldNames.billingNotes")} />

      <label htmlFor="client-update-writer-billing-amount">{t("fields.billingAmount")}</label>
      <Input
        id="client-update-writer-billing-amount"
        value={values.billingAmount}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("billingAmount", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingAmount)}
      />
      <FieldErrorMessage error={errors.billingAmount} label={t("fieldNames.billingAmount")} />

      <label htmlFor="client-update-writer-billing-due-date">{t("fields.billingDueDate")}</label>
      <Input
        id="client-update-writer-billing-due-date"
        value={values.billingDueDate}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange("billingDueDate", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.billingDueDate)}
      />
      <FieldErrorMessage error={errors.billingDueDate} label={t("fieldNames.billingDueDate")} />
      <ToneField value={values.tone} error={errors.tone} disabled={disabled} onChange={(tone) => onChange("tone", tone)} />
    </>
  );
}

export const prepaidRequestDefinition: ProductDefinition<PrepaidRequestValues, ClientUpdateWriterResult> = {
  productId: PRODUCT_ID,
  scenarioId: "client_update_writer.prepaid_request_v1",
  messageScope: "prepaid_request",
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
// finding: the two used to list the same three modes independently; labels now live in the
// product's `modes.<id>` messages) -- `Record<ModeId, ...>`
// also makes a missing mode a compile error instead of needing a runtime exhaustiveness check.
// Each mode's own V is a distinct, incompatible values shape (see the docstring above); `any`
// here is the map's value type only, not a loosening of any individual mode's own
// ProductDefinition<V, R> declaration above.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyModeDefinition = ProductDefinition<any, ClientUpdateWriterResult>;

const MODE_DEFINITIONS: Record<ModeId, AnyModeDefinition> = {
  update: updateDefinition,
  reply_draft: replyDraftDefinition,
  prepaid_request: prepaidRequestDefinition,
};
const MODE_IDS = Object.keys(MODE_DEFINITIONS) as ModeId[];

export type ClientUpdateWriterProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function ClientUpdateWriterProduct({ client, onEvent, visitId }: ClientUpdateWriterProductProps) {
  const t = useProductT();
  const [modeId, setModeId] = useState<ModeId>("update");
  // Code review finding: `key={modeId}` below unmounts the active mode's ProductRunPage the
  // instant another mode is picked -- its cleanup aborts the in-flight poll/result fetch, but the
  // backend keeps running an already-accepted scenario (a provider call the user has no way to
  // get back). Switching mode mid-run
  // silently abandoned that run's result. Disabling the mode switch for the duration of a
  // submit/run (mirroring how the form's own fields are already disabled then) is simpler and
  // safer than trying to preserve/reattach the run across a remount, and needs no changes to the
  // shared runtime's own single-mount contract.
  const [busy, setBusy] = useState(false);
  // The `disabled` attribute is the real, sufficient guard in an actual browser; this handler-level
  // check is a second, independent guard against the actual mode-switching side effect (rather
  // than only a DOM affordance a test environment's click simulation might not honor identically).
  function handleModeChange(id: ModeId) {
    if (busy) {
      return;
    }
    setModeId(id);
  }

  return (
    <>
      <fieldset>
        <legend>{t("modes.legend")}</legend>
        {MODE_IDS.map((id) => (
          <label key={id}>
            <input
              type="radio"
              name="client-update-writer-mode"
              value={id}
              checked={id === modeId}
              disabled={busy}
              onChange={() => handleModeChange(id)}
            />
            {t(`modes.${id}`)}
          </label>
        ))}
      </fieldset>
      <ProductRunPage
        key={modeId}
        definition={MODE_DEFINITIONS[modeId]}
        client={client}
        onEvent={onEvent}
        onBusyChange={setBusy}
        visitId={visitId}
      />
    </>
  );
}
