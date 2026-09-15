"use client";

import type { ChangeEvent } from "react";

/**
 * Shared across every product's form -- extracted once a second product (Client Update Writer)
 * declared the exact same tone list ProposalAI already had (code review finding).
 */
export const TONE_OPTIONS = ["neutral", "warm", "firm"] as const;
export type Tone = (typeof TONE_OPTIONS)[number];

/**
 * The `<select>` + option list every product's own tone field wraps in its own `<label>`/error
 * markup -- code review finding: Client Update Writer's `ToneField` had reimplemented this exact
 * option-mapping markup instead of reusing what ProposalAI already had. Each product still owns
 * its own label text, placeholder option, and (optional) validation error around this, since
 * ProposalAI's tone is optional with no error state and Client Update Writer's is required with
 * one -- only the genuinely identical part (the `<select>` itself) is shared.
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
    <select
      id={id}
      value={value}
      onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value as Tone | "")}
      disabled={disabled}
      aria-invalid={ariaInvalid}
    >
      <option value="">{placeholderLabel}</option>
      {TONE_OPTIONS.map((tone) => (
        <option key={tone} value={tone}>
          {tone}
        </option>
      ))}
    </select>
  );
}
