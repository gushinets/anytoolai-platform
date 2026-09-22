"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { LanguageSwitcher, LocaleProvider } from "../i18n";
import type { RegisteredProduct } from "./registry";
import type { ProductRunEvent } from "./runtime/productDefinition";

/**
 * Composition-layer wrapper around every registered product on `/products/{productId}`: owns the
 * locale provider and the one language selector so a newly registered product gets both for free.
 * The provider never remounts the product (no `key={locale}`), so form values and run state survive
 * a language switch.
 */
export function ProductPageShell({
  product,
  client,
  onEvent,
  visitId,
}: {
  product: RegisteredProduct;
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
}) {
  const { Component } = product;
  return (
    <LocaleProvider productMessages={product.messages}>
      <LanguageSwitcher />
      <Component key={product.productId} client={client} onEvent={onEvent} visitId={visitId} />
    </LocaleProvider>
  );
}
