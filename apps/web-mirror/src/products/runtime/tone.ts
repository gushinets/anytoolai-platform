/**
 * Shared across every product's form -- extracted once a second product (Client Update Writer)
 * declared the exact same tone list ProposalAI already had (code review finding).
 */
export const TONE_OPTIONS = ["neutral", "warm", "firm"] as const;
export type Tone = (typeof TONE_OPTIONS)[number];
