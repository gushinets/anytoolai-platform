"use client";

import { useContext, useEffect, useRef, useState } from "react";
import { useIsomorphicLayoutEffect } from "../../lib/useIsomorphicLayoutEffect";
import { ProductShellContext } from "../runtime/ProductShellContext";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import type { AttachProps } from "../runtime/attachSession";
import { ResolvedProductRunPage } from "../runtime/ProductRunPage";
import { ProductSelectionStatus, useProductSelection } from "../runtime/useProductSelection";
import type { ProductDefinition, ProductRunEvent } from "../runtime/productDefinition";
import { ModeSwitch } from "./ModeSwitch";

// Each mode's own values shape is distinct and incompatible, so the mode list can only hold the
// definitions loosely; this is the list's element type only, not a loosening of any individual
// mode's own `ProductDefinition<V, R>` declaration.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyModeDefinition<R> = ProductDefinition<any, R>;

export type ProductMode<Id extends string, R> = { id: Id; label: string; definition: AnyModeDefinition<R> };

/** Each mode owns its definition; selection resolves the mode/session before mounting its runtime.
 * Switching a mode remounts incompatible form values and stays disabled while a run is locked. */
export function MultiModeProduct<Id extends string, R>({
  client,
  onEvent,
  visitId,
  legend,
  name,
  modes,
  ...attach
}: AttachProps & {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
  legend: string;
  /** The radio group's `name`, unique per product. */
  name: string;
  /** The first mode is the initial one. */
  modes: readonly [ProductMode<Id, R>, ...ProductMode<Id, R>[]];
}) {
  const [locked, setLocked] = useState(false);
  const selection = useProductSelection(client, modes.map((mode) => mode.definition), attach);
  const { state } = selection;
  const mode = modes.find((mode) => state.kind === "ready" && mode.definition.scenarioId === state.selection.scenarioId) ?? modes[0];
  const containerRef = useRef<HTMLDivElement>(null);
  const focusFreshFormRef = useRef(false);
  const shell = useContext(ProductShellContext);
  useIsomorphicLayoutEffect(() => {
    if (state.kind === "ready" || !attach.attachSessionId) return;
    shell?.reportBusy(true);
    return () => shell?.reportBusy(false);
  }, [shell, state.kind, attach.attachSessionId]);
  useEffect(() => {
    if (!focusFreshFormRef.current || state.kind !== "ready" || locked) return;
    const selected = containerRef.current?.querySelector<HTMLInputElement>('input[type="radio"]:checked:not(:disabled)');
    if (selected) {
      selected.focus();
      focusFreshFormRef.current = false;
    }
  }, [state.kind, locked]);
  return (
    <div ref={containerRef}>
      <ModeSwitch legend={legend} name={name} options={modes} value={mode.id}
        disabled={locked || state.kind !== "ready"}
        onChange={(id) => {
          const mode = modes.find((candidate) => candidate.id === id);
          if (mode) selection.selectForm(mode.definition.scenarioId);
        }} />
      {state.kind !== "ready" ? <ProductSelectionStatus selection={{ ...selection, discard: () => {
        focusFreshFormRef.current = true;
        selection.discard();
      } }} /> : <ResolvedProductRunPage
        key={mode.id}
        definition={mode.definition}
        client={client}
        onEvent={onEvent}
        onLockedChange={setLocked}
        visitId={visitId}
        selection={state.selection}
        onAttachBegin={attach.onAttachBegin}
        onAttachEnd={attach.onAttachEnd}
      />}
    </div>
  );
}
