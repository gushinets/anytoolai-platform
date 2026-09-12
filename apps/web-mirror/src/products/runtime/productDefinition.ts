import type { ComponentType } from "react";

/**
 * Funnel events the shared runtime emits (product viewed -> form started -> form submitted ->
 * scenario completed/result viewed -> copy activation). Never carries prompt text, result text,
 * or clipboard contents -- only ids/status, matching ANY-453's "keep ... user text out of event
 * payloads" requirement. Real dispatch is ANY-17's; this is the injectable callback contract.
 */
export type ProductRunEvent =
  | { type: "product_viewed" }
  | { type: "form_started" }
  | { type: "form_submitted" }
  | { type: "scenario_completed"; scenarioSessionId: string }
  | { type: "copy_activated"; scenarioSessionId: string };

export type ProductFieldsProps<V> = {
  values: V;
  errors: Partial<Record<keyof V, string>>;
  /** True while a run is active; the product disables its own inputs. */
  disabled: boolean;
  onChange: <K extends keyof V>(field: K, value: V[K]) => void;
};

export type ProductResultProps<R> = {
  result: R;
  /** Call after a successful clipboard write; the runtime fires `copyNextActionId` from it. */
  onCopied: () => void;
};

/**
 * What a product owns, and nothing more (ANY-453: "Product modules own only their definition,
 * fields, renderer, and meaning"). `V` is the product's form values; `R` its canonical result.
 * Fields are a product-owned React component, deliberately not a declarative field schema.
 *
 * `copyNextActionId`/`onCopied` cover exactly the single-checkpoint "run to completion, then one
 * post-completion activation" shape ProposalAI proved (`copy_result` after `completed`) -- not a
 * general `waiting_for_user`/multi-checkpoint/multiple-next-action contract. `ProductRunPage`
 * currently treats any non-`copy_result`-shaped scenario (a mid-flow `waiting_for_user` needing a
 * product-chosen next action, e.g. Send-Ready's user-selected-angle checkpoint) as `unknown-error`.
 * Generalizing this is deliberately deferred, the same way the runtime itself was: to whichever
 * product first needs a non-single-checkpoint flow, so the generalization is derived from a real
 * multi-checkpoint product instead of guessed at now with none built (ANY-453's own
 * "speculative abstractions" non-goal).
 */
export type ProductDefinition<V extends Record<string, unknown>, R> = {
  productId: string;
  /**
   * The product's own known scenario id (its `scenarios.yaml`, e.g. `proposal_ai.generate_v1`).
   * `ProductRunPage` resolves this by id out of runtime config's `scenarios` array, never by
   * position -- that array already carries more than one scenario for some products (e.g.
   * `kernel_demo`'s own runtime-config response lists six), so picking `scenarios[0]` would
   * silently run whichever scenario the backend happens to list first instead of the one this
   * product actually means to run.
   */
  scenarioId: string;
  title: string;
  emptyValues: V;
  /** Client-side, for immediate feedback only -- the backend's schema stays authoritative. */
  validate: (values: V) => Partial<Record<keyof V, string>>;
  /** Form values -> the scenario-start `input` payload (the product's own input schema shape). */
  toInput: (values: V) => Record<string, unknown>;
  /** Frontend-safe canonical output -> the product's result; null means unusable. */
  extractResult: (output: Record<string, unknown>) => R | null;
  /** The next action fired after a successful copy (the product's `renderer_contract.yaml`). */
  copyNextActionId: string;
  Fields: ComponentType<ProductFieldsProps<V>>;
  Result: ComponentType<ProductResultProps<R>>;
  copy: {
    submit: string;
    running: string;
    runFailed: string;
    quotaRemaining: (remaining: number, limit: number) => string;
  };
};
