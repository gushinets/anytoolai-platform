"use client";

import { useContext, useEffect, useRef, useState } from "react";
import { getScenarioSession } from "@anytoolai/ce-kit";
import { Button, Card } from "@anytoolai/shared-ui";
import { useIsomorphicLayoutEffect } from "../../lib/useIsomorphicLayoutEffect";
import { ProductShellContext } from "../runtime/ProductShellContext";
import { ErrorState } from "../../components/ErrorState";
import { useHostT, useProductT } from "../../i18n";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import type { AttachProps } from "../runtime/attachSession";
import { callSafely } from "../runtime/callSafely";
import { ProductRunPage } from "../runtime/ProductRunPage";
import { readProductDraftScenario, saveProductDraftScenario } from "../runtime/draftStorage";
import type { ProductDefinition, ProductRunEvent } from "../runtime/productDefinition";
import { ModeSwitch } from "./ModeSwitch";
import styles from "../../components/cardStack.module.css";

// Each mode's own values shape is distinct and incompatible, so the mode list can only hold the
// definitions loosely; this is the list's element type only, not a loosening of any individual
// mode's own `ProductDefinition<V, R>` declaration.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyModeDefinition<R> = ProductDefinition<any, R>;

export type ProductMode<Id extends string, R> = { id: Id; label: string; definition: AnyModeDefinition<R> };

/**
 * A product whose modes are each their own complete `ProductDefinition` (one scenario per mode):
 * a mode selector above one `ProductRunPage`. Product-owned data is just the mode list.
 *
 * - `key={modeId}` remounts the page on a switch because modes' form values have incompatible
 *   shapes. Opt-in drafts restore per mode; other modes start from a clean form and run state.
 * - The switch is disabled while the page is locked (`onLockedChange`): a run in flight, a handoff being
 *   created or navigated to, or an attached session that is still booting. The remount would abort
 *   the poll and abandon an already-accepted, quota-consuming run whose result the user could never
 *   get back. Disabling is simpler and safer than re-attaching across a remount.
 * - `attachSessionId` (an accepted handoff's queued session) selects its mode by the backend scenario id, and is
 *   one-shot: any mode change drops it, so a later remount of that mode does not re-attach (and
 *   re-report) a session it already showed. The route's persisted copy is forgotten through
 *   `onAttachEnd`; the owner (`useAttachSession`) ignores it unless the attach actually began, so a switch
 *   after a failed boot leaves it and a reload still retries the paid-for session.
 */
export function MultiModeProduct<Id extends string, R>({
  client,
  onEvent,
  visitId,
  legend,
  name,
  modes,
  attachSessionId: initialAttachSessionId,
  onAttachBegin,
  onAttachEnd,
  onAttachDiscard,
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
  const [modeId, setModeId] = useState<Id>(modes[0].id);
  const [locked, setLocked] = useState(false);
  const [attachSessionId, setAttachSessionId] = useState(initialAttachSessionId);
  // The server cannot read tab storage; both hydration renders must show the same loading view.
  const [resolution, setResolution] = useState<"loading" | "ready" | "error" | "unavailable" | "identity-missing">("loading");
  const [attempt, setAttempt] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const focusFreshFormRef = useRef(false);
  const ownModeResolvedRef = useRef(false);
  const modesRef = useRef(modes);
  modesRef.current = modes;
  const shell = useContext(ProductShellContext);
  useIsomorphicLayoutEffect(() => {
    if (resolution === "ready" || !attachSessionId) return;
    shell?.reportBusy(true);
    return () => shell?.reportBusy(false);
  }, [shell, resolution, attachSessionId]);
  const th = useHostT();
  const t = useProductT();

  useEffect(() => {
    if (!attachSessionId) {
      if (!ownModeResolvedRef.current) {
        ownModeResolvedRef.current = true;
        const savedId = readProductDraftScenario(modesRef.current[0].definition.productId);
        const savedMode = modesRef.current.find((candidate) => candidate.definition.scenarioId === savedId && candidate.definition.draft);
        if (savedMode) setModeId(savedMode.id);
      }
      setResolution("ready");
      return;
    }
    const controller = new AbortController();
    void getScenarioSession(client, attachSessionId, { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return;
      if (!result.ok) {
        setResolution(result.error.type === "backend_error" && result.error.status === 404 ? "unavailable" : "error");
        return;
      }
      const target = modesRef.current.find((candidate) => candidate.definition.scenarioId === result.value.scenarioId);
      if (!target) {
        // A legacy response without identity cannot prove that the accepted session is invalid.
        setResolution(result.value.scenarioId === undefined ? "identity-missing" : "unavailable");
        return;
      }
      setModeId(target.id);
      setResolution("ready");
    });
    return () => controller.abort();
  }, [client, attachSessionId, attempt]);

  useEffect(() => {
    if (!focusFreshFormRef.current || resolution !== "ready" || locked) return;
    const selected = containerRef.current?.querySelector<HTMLInputElement>('input[type="radio"]:checked:not(:disabled)');
    if (selected) {
      selected.focus();
      focusFreshFormRef.current = false;
    }
  }, [resolution, locked]);

  function retryResolution() {
    setResolution("loading");
    setAttempt((previous) => previous + 1);
  }

  const mode = modes.find((candidate) => candidate.id === modeId) ?? modes[0];
  return (
    <div ref={containerRef}>
      <ModeSwitch
        legend={legend}
        name={name}
        options={modes}
        value={modeId}
        disabled={locked || resolution !== "ready"}
        onChange={(id) => {
          ownModeResolvedRef.current = true;
          const selected = modes.find((candidate) => candidate.id === id);
          if (selected?.definition.draft) saveProductDraftScenario(selected.definition.productId, selected.definition.scenarioId);
          if (attachSessionId) {
            // Persisted route state must forget the attached session too, or a reload restores it. Whether the
            // attach had begun is the owner's business (`useAttachSession`): a failed boot forgets nothing.
            callSafely(onAttachEnd);
          }
          setAttachSessionId(undefined);
          setModeId(id);
        }}
      />
      {resolution === "loading" ? <p role="status">{th("loading", { product: t("title") })}</p> :
        resolution === "unavailable" || resolution === "identity-missing" ? <Card className={styles.stack}>
          <ErrorState
            message={th(resolution === "identity-missing" ? "errors.attachmentUnrecognized" : "errors.attachmentUnavailable")}
            onRetry={resolution === "identity-missing" ? retryResolution : undefined}
            embedded
          />
          <Button variant="secondary" onClick={() => {
            callSafely(onAttachDiscard);
            focusFreshFormRef.current = true;
            setAttachSessionId(undefined);
            setResolution("loading");
          }}>{th("workspace.newTask")}</Button>
        </Card> :
        resolution === "error" ? <ErrorState message={th("errors.connectionLost")} onRetry={retryResolution} /> : <ProductRunPage
        key={mode.id}
        definition={mode.definition}
        client={client}
        onEvent={onEvent}
        onLockedChange={setLocked}
        visitId={visitId}
        attachSessionId={attachSessionId}
        onAttachBegin={onAttachBegin}
        onAttachEnd={onAttachEnd}
      />}
    </div>
  );
}
