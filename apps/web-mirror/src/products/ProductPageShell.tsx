"use client";

import type { PlatformApiClient } from "@anytoolai/ce-kit";
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";
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

/** Back to the tool list. Leaving mid-run is allowed, so instead of blocking it warns that the run
 * keeps going without the user seeing its result: on hover and keyboard focus (Escape dismisses),
 * and on touch -- where a tap would otherwise navigate in the same gesture -- the first tap reveals
 * the warning and only the next tap leaves. */
function AllToolsLink({ busy }: { busy: boolean }) {
  const th = useHostT();
  const tipId = useId();
  const [dismissed, setDismissed] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const lastPointerType = useRef("");
  useEffect(() => {
    if (!busy) {
      setRevealed(false);
    }
  }, [busy]);
  const wrapRef = useRef<HTMLSpanElement>(null);
  // Once revealed on touch, tapping anywhere else means "stay here": hide the warning again.
  useEffect(() => {
    if (!revealed) {
      return;
    }
    function dismissOutside(event: Event) {
      if (!wrapRef.current?.contains(event.target as Node)) {
        setRevealed(false);
      }
    }
    document.addEventListener("pointerdown", dismissOutside);
    document.addEventListener("touchstart", dismissOutside);
    return () => {
      document.removeEventListener("pointerdown", dismissOutside);
      document.removeEventListener("touchstart", dismissOutside);
    };
  }, [revealed]);
  return (
    <span
      ref={wrapRef}
      className={styles.linkWrap}
      data-dismissed={dismissed || undefined}
      data-revealed={revealed || undefined}
      onMouseLeave={() => setDismissed(false)}
      onBlur={() => setDismissed(false)}
      onKeyDown={(event) => {
        lastPointerType.current = "";
        if (event.key === "Escape") {
          setDismissed(true);
        }
      }}
    >
      <Link
        href="/"
        className={styles.allTools}
        aria-describedby={busy ? tipId : undefined}
        onPointerDown={(event) => {
          lastPointerType.current = event.pointerType;
        }}
        // A touch fires touchstart too; this also covers engines that skip the pointer type.
        onTouchStart={() => {
          lastPointerType.current = "touch";
        }}
        onClick={(event) => {
          // Consumed by this click, so a later keyboard activation (no pointer event of its own)
          // can never be mistaken for the touch that came before it.
          const touched = lastPointerType.current === "touch";
          lastPointerType.current = "";
          if (busy && touched && !revealed) {
            event.preventDefault();
            setRevealed(true);
          }
        }}
      >
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
