"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import Link from "next/link";
import { useId, useMemo, useState } from "react";
import { LanguageSwitcher, LocaleProvider, useHostT, useProductT } from "../i18n";
import type { RegisteredProduct } from "./registry";
import type { ProductRunEvent } from "./runtime/productDefinition";
import { ProductShellContext, type ProductShell } from "./runtime/ProductShellContext";
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
  const th = useHostT();
  const [busy, setBusy] = useState(false);
  // Stable identity: the run page's effect depends on it and must not re-fire every render.
  const shell = useMemo<ProductShell>(() => ({ reportBusy: setBusy }), []);
  return (
    <div className={styles.shell}>
      <nav className={styles.nav} aria-label={th("nav.label")}>
        <AllToolsLink busy={busy} />
      </nav>
      <main>
        <header className={styles.titleRow}>
          <h1>{t("title")}</h1>
          <LanguageSwitcher />
        </header>
        {/* No key here: the caller already keys ProductPageShell itself by productId (page.tsx), so
            this whole subtree -- Component included -- already remounts on a product change. */}
        <ProductShellContext.Provider value={shell}>
          <Component client={client} onEvent={onEvent} visitId={visitId} />
        </ProductShellContext.Provider>
      </main>
    </div>
  );
}

/** Back to the tool list. Leaving mid-run is allowed, so instead of blocking it warns (on hover and
 * keyboard focus, Escape dismisses) that the run keeps going without the user seeing its result. */
function AllToolsLink({ busy }: { busy: boolean }) {
  const th = useHostT();
  const tipId = useId();
  const [dismissed, setDismissed] = useState(false);
  return (
    <span
      className={styles.linkWrap}
      data-dismissed={dismissed || undefined}
      onMouseLeave={() => setDismissed(false)}
      onBlur={() => setDismissed(false)}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setDismissed(true);
        }
      }}
    >
      <Link href="/" className={styles.allTools} aria-describedby={busy ? tipId : undefined}>
        <span aria-hidden="true">‹</span> {th("nav.allTools")}
      </Link>
      {busy ? (
        <span id={tipId} role="tooltip" className={styles.tooltip}>
          {th("nav.runInProgress")}
        </span>
      ) : null}
    </span>
  );
}
