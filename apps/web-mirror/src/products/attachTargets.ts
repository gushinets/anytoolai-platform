import { isProductEnabled } from "./runtime/enabledProducts";

/** Scenarios whose product page can show an already-queued session (`attachSessionId`), i.e. the
 * targets an accepted handoff may redirect to. Kept apart from the product registry so the consent
 * route does not bundle every product. Pinned to the products by test/AcceptanceBuilderProduct. */
const ATTACHABLE_SCENARIOS: Record<string, readonly string[]> = {
  acceptance_builder: ["acceptance_builder.draft_v1"],
};

export function canAttachTarget(productId: string, scenarioId: string): boolean {
  return isProductEnabled(productId) && (ATTACHABLE_SCENARIOS[productId]?.includes(scenarioId) ?? false);
}
