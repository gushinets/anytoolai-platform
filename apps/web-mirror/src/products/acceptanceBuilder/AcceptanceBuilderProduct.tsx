"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { useProductT } from "../../i18n";
import {
  collectFieldErrors,
  requiredBackendTrimmedFieldError,
  trimBackendWhitespace,
} from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import { MultiModeProduct } from "../shared/MultiModeProduct";
import { TextAreaField } from "../shared/TextAreaField";
import { AcceptanceBuilderResultView } from "./AcceptanceBuilderResult";
import { extractCheckResult, extractDraftResult, hasCriteria, type AcceptanceBuilderResult } from "./parseAcceptanceBuilder";

// Mirrors `draft_input.schema.json` / `check_input.schema.json` maxLength.
const TEXT_MAX_LENGTH = 8000;

type DraftValues = { briefText: string };
type CheckValues = { briefText: string; deliverableText: string };

function BriefField({ values, errors, disabled, onChange }: ProductFieldsProps<DraftValues>) {
  const t = useProductT();
  return (
    <TextAreaField
      id="acceptance-builder-brief-text"
      label={t("fields.briefText")}
      placeholder={t("fields.briefTextPlaceholder")}
      help={t("fields.briefTextHelp")}
      value={values.briefText}
      error={errors.briefText}
      disabled={disabled}
      onChange={(value) => onChange("briefText", value)}
    />
  );
}

function CheckFields({ values, errors, disabled, onChange }: ProductFieldsProps<CheckValues>) {
  const t = useProductT();
  return (
    <>
      <BriefField values={values} errors={errors} disabled={disabled} onChange={onChange} />
      <TextAreaField
        id="acceptance-builder-deliverable-text"
        label={t("fields.deliverableText")}
        placeholder={t("fields.deliverableTextPlaceholder")}
        help={t("fields.deliverableTextHelp")}
        value={values.deliverableText}
        error={errors.deliverableText}
        disabled={disabled}
        onChange={(value) => onChange("deliverableText", value)}
      />
    </>
  );
}

const briefError = (values: DraftValues) => requiredBackendTrimmedFieldError(values.briefText, TEXT_MAX_LENGTH);

/** The two scenarios share one product namespace; `draft_v1` (brief -> criteria) counts as
 * activation only when it lists criteria (the draft has no verdict, see `renderer_contract.yaml`),
 * `check_v1` always shows a verdict. Neither scenario has an extra client-side decision. */
export const draftDefinition: ProductDefinition<DraftValues, AcceptanceBuilderResult> = {
  productId: "acceptance_builder",
  scenarioId: "acceptance_builder.draft_v1",
  messageScope: "draft",
  hasDescription: true,
  emptyValues: { briefText: "" },
  validate: (values) => collectFieldErrors<DraftValues>([["briefText", briefError(values)]]),
  toInput: (values) => ({ brief_text: trimBackendWhitespace(values.briefText) }),
  extractResult: extractDraftResult,
  emitsResultViewed: hasCriteria,
  Fields: BriefField,
  Result: AcceptanceBuilderResultView,
};

export const checkDefinition: ProductDefinition<CheckValues, AcceptanceBuilderResult> = {
  productId: "acceptance_builder",
  scenarioId: "acceptance_builder.check_v1",
  messageScope: "check",
  hasDescription: true,
  emptyValues: { briefText: "", deliverableText: "" },
  validate: (values) =>
    collectFieldErrors<CheckValues>([
      ["briefText", briefError(values)],
      ["deliverableText", requiredBackendTrimmedFieldError(values.deliverableText, TEXT_MAX_LENGTH)],
    ]),
  toInput: (values) => ({ brief_text: trimBackendWhitespace(values.briefText), deliverable_text: trimBackendWhitespace(values.deliverableText) }),
  extractResult: extractCheckResult,
  Fields: CheckFields,
  Result: AcceptanceBuilderResultView,
};

export type AcceptanceBuilderProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
  attachSessionId?: string;
};

/** One `ProductDefinition` per mode. An attached session (an accepted Brief Decoder handoff) is
 * always a `draft_v1` run, so only draft mode receives it. */
export function AcceptanceBuilderProduct({ client, onEvent, visitId, attachSessionId }: AcceptanceBuilderProductProps) {
  const t = useProductT();
  return (
    <MultiModeProduct
      client={client}
      onEvent={onEvent}
      visitId={visitId}
      legend={t("modes.legend")}
      name="acceptance-builder-mode"
      modes={[
        { id: "draft", label: t("modes.draft"), definition: draftDefinition },
        { id: "check", label: t("modes.check"), definition: checkDefinition },
      ]}
      attachSessionId={attachSessionId}
      attachModeId="draft"
    />
  );
}
