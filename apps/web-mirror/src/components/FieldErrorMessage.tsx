"use client";

import { useHostT, useProductT } from "../i18n";
import { assertNever } from "../products/runtime/productDefinition";
import type { FieldError } from "../products/runtime/fieldValidation";

/** Renders a structured `FieldError` in the current UI locale. `label` is the product-owned,
 * already-localized field name; product-specific rules resolve in the product's own namespace.
 * `id`/`className` are optional passthroughs so a caller can wire `aria-describedby`/layout to the
 * rendered `<p>` itself, instead of duplicating this component's own error-to-text logic locally. */
export function FieldErrorMessage({
  error,
  label,
  id,
  className,
}: {
  error: FieldError | undefined;
  label: string;
  id?: string;
  className?: string;
}) {
  const th = useHostT();
  const tp = useProductT();
  if (!error) {
    return null;
  }
  switch (error.code) {
    case "required":
      return (
        <p id={id} className={className} role="alert">
          {th("validation.required", { field: label })}
        </p>
      );
    case "outer_whitespace":
      return (
        <p id={id} className={className} role="alert">
          {th("validation.outerWhitespace", { field: label })}
        </p>
      );
    case "max_length":
      return (
        <p id={id} className={className} role="alert">
          {th("validation.maxLength", { field: label, maxLength: error.maxLength })}
        </p>
      );
    case "product":
      return (
        <p id={id} className={className} role="alert">
          {tp(error.key)}
        </p>
      );
    default:
      // Code review finding: no exhaustiveness arm, unlike every other closed-union switch in this
      // runtime (docs/agent/coding-conventions.md "Exhaustiveness") -- a future FieldError variant
      // would silently render nothing instead of failing typecheck.
      return assertNever(error);
  }
}
