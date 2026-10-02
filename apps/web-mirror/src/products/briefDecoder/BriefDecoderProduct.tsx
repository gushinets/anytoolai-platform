"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import {
  collectFieldErrors,
  requiredBackendTrimmedFieldError,
  trimBackendWhitespace,
  type FieldError,
} from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import { TextAreaField } from "../shared/TextAreaField";
import { BriefDecoderResultView } from "./BriefDecoderResult";
import { extractBriefDecoderResult, hasQuestions, type BriefDecoderResult } from "./parseBriefDecoder";

// Mirrors `brief_decoder.decode_input_v1`'s `brief_text` maxLength.
const BRIEF_TEXT_MAX_LENGTH = 8000;

export type BriefDecoderValues = { briefText: string };

function validate(values: BriefDecoderValues): Partial<Record<keyof BriefDecoderValues, FieldError>> {
  return collectFieldErrors<BriefDecoderValues>([["briefText", requiredBackendTrimmedFieldError(values.briefText, BRIEF_TEXT_MAX_LENGTH)]]);
}

function BriefDecoderFields({ values, errors, disabled, onChange }: ProductFieldsProps<BriefDecoderValues>) {
  const t = useProductT();
  return (
    <TextAreaField
      id="brief-decoder-brief-text"
      label={t("fields.briefText")}
      placeholder={t("fields.briefTextPlaceholder")}
      help={t("fields.briefTextHelp")}
      value={values.briefText}
      error={errors.briefText}
      disabled={disabled}
      minHeight={200}
      onChange={(value) => onChange("briefText", value)}
    />
  );
}

/** Brief Decoder's product meaning only: the field, the `brief_decoder.decode_input_v1` mapping,
 * the four-part composite result, and the activation rule -- `web.result_viewed` only for a
 * non-empty clarifying-question list (a zero-question run still renders and still completes, see
 * the contract). */
export const briefDecoderDefinition: ProductDefinition<BriefDecoderValues, BriefDecoderResult> = {
  productId: "brief_decoder",
  scenarioId: "brief_decoder.decode_v1",
  messageScope: "decode",
  hasDescription: true,
  emptyValues: { briefText: "" },
  validate,
  toInput: (values) => ({ brief_text: trimBackendWhitespace(values.briefText) }),
  extractResult: extractBriefDecoderResult,
  emitsResultViewed: hasQuestions,
  // `handoffs.yaml`: `brief_decoder_to_acceptance_builder_v1` (immediate, user-confirmed).
  handoff: { handoffDefinitionId: "brief_decoder_to_acceptance_builder_v1", targetProductId: "acceptance_builder" },
  Fields: BriefDecoderFields,
  Result: BriefDecoderResultView,
};

export type BriefDecoderProductProps = {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
};

export function BriefDecoderProduct({ client, onEvent, visitId }: BriefDecoderProductProps) {
  return <ProductRunPage definition={briefDecoderDefinition} client={client} onEvent={onEvent} visitId={visitId} />;
}
