"use client";

import type { ChangeEvent } from "react";
import { Select } from "@anytoolai/shared-ui";

// Product vocabulary shared by the products whose input schemas declare this `tone` enum, so it
// lives here (shared across products) and not in `products/runtime/`, which must hold no product
// meaning (docs/architecture/frontend-boundaries.md). The backend schemas own the enum; this is a
// checked mirror -- test/tone.test.tsx fails if any of those schemas drifts from it. Options and
// the `Tone` type derive from this one map, so there is no second list to keep in sync.
const TONE_BY_VALUE = { neutral: true, warm: true, firm: true } as const;
export type Tone = keyof typeof TONE_BY_VALUE;
export const TONE_OPTIONS = Object.keys(TONE_BY_VALUE) as readonly Tone[];

export function isTone(value: string): value is Tone {
  return Object.hasOwn(TONE_BY_VALUE, value);
}

/**
 * The `<select>` + option list every product's own tone field wraps in its own `<label>`/error
 * markup. Each product still owns its label text, placeholder option, and (optional) validation
 * error around this, since ProposalAI's tone is optional with no error state and Client Update
 * Writer's is required with one -- only the genuinely identical part is shared.
 */
export function ToneSelect({
  id,
  value,
  onChange,
  disabled,
  placeholderLabel,
  ariaInvalid,
}: {
  id: string;
  value: Tone | "";
  onChange: (tone: Tone | "") => void;
  disabled: boolean;
  placeholderLabel: string;
  ariaInvalid?: boolean;
}) {
  return (
    <Select
      id={id}
      value={value}
      onChange={(event: ChangeEvent<HTMLSelectElement>) =>
        onChange(isTone(event.target.value) ? event.target.value : "")
      }
      disabled={disabled}
      aria-invalid={ariaInvalid}
    >
      <option value="">{placeholderLabel}</option>
      {TONE_OPTIONS.map((tone) => (
        <option key={tone} value={tone}>
          {tone}
        </option>
      ))}
    </Select>
  );
}
