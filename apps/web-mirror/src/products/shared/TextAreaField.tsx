"use client";

import type { ChangeEvent, CSSProperties } from "react";
import { TextArea } from "@anytoolai/shared-ui";
import { FieldErrorMessage } from "../../components/FieldErrorMessage";
import type { FieldError } from "../runtime/fieldValidation";
import styles from "./TextAreaField.module.css";

/** A labelled long-text field with help text and a localized error, wired for screen readers
 * (`aria-invalid`, `aria-describedby`). Ids derive from `id`: `{id}-help`, `{id}-error`. */
export function TextAreaField({
  id,
  label,
  placeholder,
  help,
  value,
  error,
  disabled,
  minHeight,
  onChange,
}: {
  id: string;
  label: string;
  placeholder: string;
  help: string;
  value: string;
  error: FieldError | undefined;
  disabled: boolean;
  minHeight?: number;
  onChange: (value: string) => void;
}) {
  return (
    <div className={styles.fieldGroup} style={minHeight ? ({ "--textarea-min-height": `${minHeight}px` } as CSSProperties) : undefined}>
      <label htmlFor={id}>{label}</label>
      <TextArea
        id={id}
        className={styles.textArea}
        value={value}
        placeholder={placeholder}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange(event.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={`${id}-help${error ? ` ${id}-error` : ""}`}
      />
      <p id={`${id}-help`} className={styles.help}>
        {help}
      </p>
      <FieldErrorMessage id={`${id}-error`} className={styles.error} error={error} label={label} />
    </div>
  );
}
