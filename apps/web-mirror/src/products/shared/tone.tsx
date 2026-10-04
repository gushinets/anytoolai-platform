"use client";

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
