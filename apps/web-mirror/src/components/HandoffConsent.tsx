"use client";

import { useEffect, useState } from "react";
import {
  acceptHandoff,
  createLocalStorageAdapter,
  declineHandoff,
  getHandoff,
  isHandoffAcceptanceFailed,
  isHandoffExpired,
  isHandoffNotActionable,
  isHandoffNotFound,
  isHandoffSourceInvalid,
  isQuotaExhausted,
  type HandoffPreview,
  type PlatformApiClient,
  type PlatformApiError,
} from "@anytoolai/ce-kit";

export type HandoffConsentProps = {
  client: PlatformApiClient;
  handoffToken: string;
};

// ponytail: hand-synced against the backend's HandoffStatus enum
// (packages/backend/platform-core/.../handoffs/models.py) -- the wire schema types `status` as a
// bare string, not an enum, so there is no generated source of truth to import here. If the
// backend adds a new terminal status, update this set too, or Accept/Decline will render on an
// already-terminal handoff.
const TERMINAL_STATUSES = new Set(["accepted", "declined", "consumed", "expired", "failed"]);

type ViewState =
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "safe-error" }
  | { kind: "consent"; preview: HandoffPreview; pending: "accept" | "decline" | null; actionError: string | null }
  | { kind: "terminal"; preview: HandoffPreview };

function stateForPreview(preview: HandoffPreview): ViewState {
  return TERMINAL_STATUSES.has(preview.status)
    ? { kind: "terminal", preview }
    : { kind: "consent", preview, pending: null, actionError: null };
}

function viewStateFromResult(result: Awaited<ReturnType<typeof getHandoff>>): ViewState {
  if (!result.ok) {
    return isHandoffNotFound(result.error) ? { kind: "not-found" } : { kind: "safe-error" };
  }
  return stateForPreview(result.value);
}

/**
 * State machine for the backend-owned handoff consent page. Renders only the fields the backend
 * safe preview carries -- no provider/model, prompt, or raw artifact data ever reaches this
 * component. `preview.preview` is a bounded, config-mapped `dict[str, Any]` on the wire, so it is
 * always rendered as opaque key/value pairs, never by assuming specific keys.
 */
export function HandoffConsent({ client, handoffToken }: HandoffConsentProps) {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const [guestId, setGuestId] = useState<string | undefined>(undefined);

  // The backend attributes an accept's quota to `guest_id` if given, falling back to the
  // handoff's original creator otherwise -- so the person actually clicking Accept needs their
  // own guest identity, not the creator's. Resolved alongside the preview fetch (not after) so
  // Accept/Decline never render before guestId has settled -- otherwise a click that races the
  // identity call would silently fall back to creator-attribution again. A resolution failure
  // just leaves guestId unset, matching that same pre-existing fallback rather than blocking the
  // page.
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getHandoff(client, handoffToken, { signal: controller.signal }),
      // createGuestIdentity() has no signal option (it's single-flight and shared across every
      // caller on this client instance, so one caller cancelling could not cancel the others) --
      // a fast unmount/token change leaves this POST running in the background for a discarded
      // result, same as any other fire-and-forget identity call in ce-kit today.
      client.createGuestIdentity({ storage: createLocalStorageAdapter(window.localStorage) }),
    ]).then(([previewResult, guestResult]) => {
      if (controller.signal.aborted) {
        return;
      }
      if (guestResult.ok) {
        setGuestId(guestResult.value.guestId);
      }
      setState(viewStateFromResult(previewResult));
    });
    return () => {
      controller.abort();
    };
  }, [client, handoffToken]);

  // A stale accept/decline can race an already-terminal token (expired, already accepted/declined,
  // or a failed target execution). Rather than retry the mutation, refetch the authoritative
  // preview via getHandoff() and render whatever terminal state it reports -- this is what makes a
  // consumed token unreplayable from the client's side: the backend's current state always wins.
  async function resolveActionError(error: PlatformApiError): Promise<void> {
    const shouldRefetch =
      isHandoffExpired(error) ||
      isHandoffNotActionable(error) ||
      isHandoffAcceptanceFailed(error) ||
      isHandoffSourceInvalid(error) ||
      isQuotaExhausted(error);
    if (!shouldRefetch) {
      setState((prev) =>
        prev.kind === "consent" ? { ...prev, pending: null, actionError: "That action could not be completed. Please try again." } : prev,
      );
      return;
    }
    const refetched = await getHandoff(client, handoffToken);
    setState(viewStateFromResult(refetched));
  }

  async function runAction(
    kind: "accept" | "decline",
    mutate: () => ReturnType<typeof acceptHandoff>,
  ) {
    setState((prev) => (prev.kind === "consent" ? { ...prev, pending: kind, actionError: null } : prev));
    const result = await mutate();
    if (result.ok) {
      setState(stateForPreview(result.value));
    } else {
      await resolveActionError(result.error);
    }
  }

  function handleAccept() {
    return runAction("accept", () => acceptHandoff(client, handoffToken, { guestId }));
  }

  function handleDecline() {
    return runAction("decline", () => declineHandoff(client, handoffToken));
  }

  if (state.kind === "loading") {
    return <p role="status">Loading handoff…</p>;
  }
  if (state.kind === "not-found") {
    return <p role="alert">This handoff link is not valid.</p>;
  }
  if (state.kind === "safe-error") {
    return <p role="alert">Something went wrong loading this handoff. Please try again.</p>;
  }

  const { preview } = state;
  return (
    <main>
      <dl>
        <dt>From</dt>
        <dd>{preview.sourceProductDisplayName}</dd>
        <dt>To</dt>
        <dd>{preview.targetProductDisplayName}</dd>
        <dt>Expires</dt>
        <dd>{preview.expiresAt}</dd>
        <dt>Status</dt>
        <dd>{preview.status}</dd>
        {Object.entries(preview.preview).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd>
          </div>
        ))}
      </dl>
      {state.kind === "consent" ? (
        <>
          <button type="button" onClick={handleAccept} disabled={state.pending !== null}>
            Accept
          </button>
          <button type="button" onClick={handleDecline} disabled={state.pending !== null}>
            Decline
          </button>
          {state.actionError ? <p role="alert">{state.actionError}</p> : null}
        </>
      ) : null}
    </main>
  );
}
