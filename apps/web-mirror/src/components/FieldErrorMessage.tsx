"use client";

import { useHostT, useProductT } from "../i18n";
import type { FieldError } from "../products/runtime/fieldValidation";

/** Renders a structured `FieldError` in the current UI locale. `label` is the product-owned,
 * already-localized field name; product-specific rules resolve in the product's own namespace. */
export function FieldErrorMessage({ error, label }: { error: FieldError | undefined; label: string }) {
  const th = useHostT();
  const tp = useProductT();
  if (!error) {
    return null;
  }
  switch (error.code) {
    case "required":
      return <p role="alert">{th("validation.required", { field: label })}</p>;
    case "outer_whitespace":
      return <p role="alert">{th("validation.outerWhitespace", { field: label })}</p>;
    case "max_length":
      return <p role="alert">{th("validation.maxLength", { field: label, maxLength: error.maxLength })}</p>;
    case "product":
      return <p role="alert">{tp(error.key)}</p>;
  }
}
