import type { ComponentType } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { ProposalAIProduct } from "./proposalAi/ProposalAIProduct";
import type { ProductRunEvent } from "./runtime/productDefinition";

export type RegisteredProduct = {
  productId: string;
  enabled: boolean;
  Component: ComponentType<{ client: PlatformApiClient; onEvent?: (event: ProductRunEvent) => void }>;
};

/** Static product registry for `/products/{productId}`. This is the composition layer
 * (`docs/architecture/frontend-boundaries.md`): the one place allowed to import both the shared
 * runtime and individual products. The shared runtime itself never imports a product. */
const PRODUCTS: readonly RegisteredProduct[] = [{ productId: "proposal_ai", enabled: true, Component: ProposalAIProduct }];

export function getRegisteredProduct(productId: string): RegisteredProduct | null {
  const product = PRODUCTS.find((candidate) => candidate.productId === productId);
  return product && product.enabled ? product : null;
}
