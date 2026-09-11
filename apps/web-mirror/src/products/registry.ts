import type { ComponentType } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ProposalAIProduct } from "./proposalAi/ProposalAIProduct";

export type ProductDefinition = {
  productId: string;
  enabled: boolean;
  Component: ComponentType<{ client: PlatformApiClient }>;
};

/** Static product registry for `/products/{productId}`. One entry per product owns only its own
 * component -- per ANY-453's team-lead guidance (docs/exec-plans/active/
 * any-453-shared-web-product-runtime-foundation.md): no shared product-definition contract until
 * a second product needs the same shape. */
const PRODUCTS: readonly ProductDefinition[] = [{ productId: "proposal_ai", enabled: true, Component: ProposalAIProduct }];

export function getProductDefinition(productId: string): ProductDefinition | null {
  const definition = PRODUCTS.find((product) => product.productId === productId);
  return definition && definition.enabled ? definition : null;
}
