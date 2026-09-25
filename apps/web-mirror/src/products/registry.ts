import type { ComponentType } from "react";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import type { ProductMessagesByLocale } from "../i18n";
import { BriefDecoderProduct } from "./briefDecoder/BriefDecoderProduct";
import { BRIEF_DECODER_MESSAGES } from "./briefDecoder/messages";
import { ClientUpdateWriterProduct } from "./clientUpdateWriter/ClientUpdateWriterProduct";
import { CLIENT_UPDATE_WRITER_MESSAGES } from "./clientUpdateWriter/messages";
import { ProposalAIProduct } from "./proposalAi/ProposalAIProduct";
import { PROPOSAL_AI_MESSAGES } from "./proposalAi/messages";
import type { ProductRunEvent } from "./runtime/productDefinition";

export type RegisteredProduct = {
  productId: string;
  enabled: boolean;
  /** The shell renders each locale's title and supplies the language selector and locale state. */
  messages: ProductMessagesByLocale & Record<keyof ProductMessagesByLocale, { title: string }>;
  Component: ComponentType<{
    client: PlatformApiClient;
    onEvent?: (event: ProductRunEvent) => void;
    /** See `ProductRunPageProps.visitId`'s own docstring -- a fresh id per real landing on this
     * product, used to scope the shared runtime's once-per-visit event dedupe (code review
     * finding: a bare productId-keyed dedupe undercounted a genuine revisit to the same product). */
    visitId?: string;
  }>;
};

/** Static product registry for `/products/{productId}`. This is the composition layer
 * (`docs/architecture/frontend-boundaries.md`): the one place allowed to import both the shared
 * runtime and individual products. The shared runtime itself never imports a product. */
const configuredIds = process.env.NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS;
const enabledIds = configuredIds === undefined ? null : new Set(configuredIds.split(",").map((id) => id.trim()).filter(Boolean));

const PRODUCT_DEFINITIONS: readonly Omit<RegisteredProduct, "enabled">[] = [
  { productId: "proposal_ai", messages: PROPOSAL_AI_MESSAGES, Component: ProposalAIProduct },
  {
    productId: "client_update_writer",
    messages: CLIENT_UPDATE_WRITER_MESSAGES,
    Component: ClientUpdateWriterProduct,
  },
  { productId: "brief_decoder", messages: BRIEF_DECODER_MESSAGES, Component: BriefDecoderProduct },
];

for (const productId of enabledIds ?? []) {
  // kernel_demo is the backend-only product used by the credential-free production smoke.
  if (
    productId !== "kernel_demo" &&
    !PRODUCT_DEFINITIONS.some((product) => product.productId === productId)
  ) {
    throw new Error(`Web product is not registered: ${productId}`);
  }
}

const PRODUCTS: readonly RegisteredProduct[] = PRODUCT_DEFINITIONS.map((product) => ({
  ...product,
  enabled: enabledIds === null || enabledIds.has(product.productId),
}));

export function getRegisteredProduct(productId: string): RegisteredProduct | null {
  const product = PRODUCTS.find((candidate) => candidate.productId === productId);
  return product && product.enabled ? product : null;
}

/** Every registered product, enabled or not -- lets tests (translation completeness) cover a newly
 * registered product without naming it. */
export function listRegisteredProducts(): readonly RegisteredProduct[] {
  return PRODUCTS;
}
