"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { LanguageSwitcher, LocaleProvider, useProductT } from "../i18n";
import type { RegisteredProduct } from "./registry";
import type { ProductRunEvent } from "./runtime/productDefinition";
import { ProductShellContext } from "./runtime/ProductShellContext";
import styles from "./ProductPageShell.module.css";

/**
 * Composition-layer wrapper around every registered product on `/products/{productId}`: owns the
 * locale provider and the one language selector for every registered product.
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
      <ProductPageContent Component={Component} client={client} onEvent={onEvent} visitId={visitId} />
    </LocaleProvider>
  );
}

function ProductPageContent({ Component, client, onEvent, visitId }: Pick<RegisteredProduct, "Component"> & {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
}) {
  const t = useProductT();
  return (
    <div className={styles.shell}>
      <header className={styles.titleRow}>
        <h1>{t("title")}</h1>
        <LanguageSwitcher />
      </header>
      {/* No key here: the caller already keys ProductPageShell itself by productId (page.tsx), so
          this whole subtree -- Component included -- already remounts on a product change. */}
      <ProductShellContext.Provider value={true}>
        <Component client={client} onEvent={onEvent} visitId={visitId} />
      </ProductShellContext.Provider>
    </div>
  );
}
