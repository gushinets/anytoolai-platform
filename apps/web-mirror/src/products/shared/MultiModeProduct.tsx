"use client";

import { useState } from "react";
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
 * - `attachSessionId` (an accepted handoff's queued session) goes to `attachModeId` only, and is
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
  attachModeId,
}: AttachProps & {
  client: PlatformApiClient;
  onEvent?: (event: ProductRunEvent) => void;
  visitId?: string;
  legend: string;
  /** The radio group's `name`, unique per product. */
  name: string;
  /** The first mode is the initial one. */
  modes: readonly [ProductMode<Id, R>, ...ProductMode<Id, R>[]];
  attachModeId?: Id;
}) {
  const [modeId, setModeId] = useState<Id>(modes[0].id);
  const [locked, setLocked] = useState(false);
  const [attachSessionId, setAttachSessionId] = useState(initialAttachSessionId);
  const mode = modes.find((candidate) => candidate.id === modeId) ?? modes[0];
  return (
    <>
      <ModeSwitch
        legend={legend}
        name={name}
        options={modes}
        value={modeId}
        disabled={locked}
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
      <ProductRunPage
        key={mode.id}
        definition={mode.definition}
        client={client}
        onEvent={onEvent}
        onLockedChange={setLocked}
        visitId={visitId}
        attachSessionId={mode.id === attachModeId ? attachSessionId : undefined}
        onAttachBegin={onAttachBegin}
        onAttachEnd={onAttachEnd}
      />
    </>
  );
}
