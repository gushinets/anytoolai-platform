"use client";

import type { ChangeEvent } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { TextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import { useProductT } from "../../i18n";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { collectFieldErrors, type FieldError } from "../runtime/fieldValidation";
import type { ProductDefinition, ProductFieldsProps, ProductRunEvent } from "../runtime/productDefinition";
import styles from "./BriefDecoderProduct.module.css";
import { BriefDecoderResultView } from "./BriefDecoderResult";
import { extractBriefDecoderResult, hasQuestions, trimBriefText, type BriefDecoderResult } from "./parseBriefDecoder";

// Mirrors `brief_decoder.decode_input_v1`'s `brief_text` maxLength.
const BRIEF_TEXT_MAX_LENGTH = 8000;

export type BriefDecoderValues = { briefText: string };

// Pasted briefs often end in a newline, and the shared validator's JS `trim()` disagrees with the
// backend's Python `\s` on a few code points, so this field is trimmed (not rejected) with the
// backend's own notion of whitespace, and `toInput` sends exactly what was validated.
function briefTextError(value: string): FieldError | undefined {
  const trimmed = trimBriefText(value);
  if (trimmed.length === 0) {
    return { code: "required" };
  }
  return [...trimmed].length > BRIEF_TEXT_MAX_LENGTH ? { code: "max_length", maxLength: BRIEF_TEXT_MAX_LENGTH } : undefined;
}

function validate(values: BriefDecoderValues): Partial<Record<keyof BriefDecoderValues, FieldError>> {
  return collectFieldErrors<BriefDecoderValues>([["briefText", briefTextError(values.briefText)]]);
}

function BriefDecoderFields({ values, errors, disabled, onChange }: ProductFieldsProps<BriefDecoderValues>) {
  const t = useProductT();
  return (
    <div className={styles.fieldGroup}>
      <label htmlFor="brief-decoder-brief-text">{t("fields.briefText")}</label>
      <TextArea
        id="brief-decoder-brief-text"
        className={styles.briefTextArea}
        value={values.briefText}
        placeholder={t("fields.briefTextPlaceholder")}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange("briefText", event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(errors.briefText)}
        aria-describedby={`brief-decoder-brief-text-help${errors.briefText ? " brief-decoder-brief-text-error" : ""}`}
      />
      <p id="brief-decoder-brief-text-help" className={styles.help}>
        {t("fields.briefTextHelp")}
      </p>
      <FieldErrorMessage
        id="brief-decoder-brief-text-error"
        className={styles.error}
        error={errors.briefText}
        label={t("fields.briefText")}
      />
    </div>
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
  hasStartAnother: true,
  emptyValues: { briefText: "" },
  validate,
  toInput: (values) => ({ brief_text: trimBriefText(values.briefText) }),
  extractResult: extractBriefDecoderResult,
  emitsResultViewed: hasQuestions,
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
