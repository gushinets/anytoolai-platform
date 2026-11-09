"use client";

import { useContext, useEffect, useRef, useState } from "react";
import { getScenarioSession } from "@anytoolai/ce-kit";
import { useIsomorphicLayoutEffect } from "../../lib/useIsomorphicLayoutEffect";
import { ProductShellContext } from "../runtime/ProductShellContext";
import { ErrorState } from "../../components/ErrorState";
import { useHostT, useProductT } from "../../i18n";
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import type { AttachProps } from "../runtime/attachSession";
import { callSafely } from "../runtime/callSafely";
import { ProductRunPage } from "../runtime/ProductRunPage";
import type { ProductDefinition, ProductRunEvent } from "../runtime/productDefinition";
import { ModeSwitch } from "./ModeSwitch";

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
 * - `key={modeId}` remounts the page on a switch, so a mode always starts from a clean form and run
 *   state; that is load-bearing, since the modes' form values have incompatible shapes.
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
  const [resolution, setResolution] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const modesRef = useRef(modes);
  modesRef.current = modes;
  const shell = useContext(ProductShellContext);
  useIsomorphicLayoutEffect(() => {
    if (resolution === "ready" || !initialAttachSessionId) return;
    shell?.reportBusy(true);
    return () => shell?.reportBusy(false);
  }, [shell, resolution, initialAttachSessionId]);
  const th = useHostT();
  const t = useProductT();

  useEffect(() => {
    if (!initialAttachSessionId) {
      setResolution("ready");
      return;
    }
    const controller = new AbortController();
    void getScenarioSession(client, initialAttachSessionId, { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return;
      const target = result.ok
        ? modesRef.current.find((candidate) => candidate.definition.scenarioId === result.value.scenarioId)
        : undefined;
      if (!target) {
        setResolution("error");
        return;
      }
      setModeId(target.id);
      setResolution("ready");
    });
    return () => controller.abort();
  }, [client, initialAttachSessionId, attempt]);

  const mode = modes.find((candidate) => candidate.id === modeId) ?? modes[0];
  return (
    <>
      <ModeSwitch
        legend={legend}
        name={name}
        options={modes}
        value={modeId}
        disabled={locked || resolution !== "ready"}
        onChange={(id) => {
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
        resolution === "error" ? <ErrorState message={th("errors.connectionLost")} onRetry={() => {
          setResolution("loading");
          setAttempt((previous) => previous + 1);
        }} /> : <ProductRunPage
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
    </>
  );
}
