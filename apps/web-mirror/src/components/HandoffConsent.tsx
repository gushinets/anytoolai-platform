"use client";

import { useEffect, useState } from "react";
import {
  acceptHandoff,
  createWindowLocalStorageAdapter,
  DEFAULT_GUEST_STORAGE_KEY,
  declineHandoff,
  getHandoff,
  isHandoffActionRefetchable,
  isHandoffGuestIdentityInvalid,
  isHandoffNotFound,
  networkError,
  type GuestIdentityResult,
  type HandoffPreview,
  type PlatformApiClient,
  type PlatformApiError,
  type PlatformApiResult,
} from "@anytoolai/ce-kit";

// createWindowLocalStorageAdapter() already guards against window.localStorage itself throwing
// synchronously (privacy-hardened browsers, storage-denied sandboxed iframes) -- null here
// degrades to "no persisted guest id" (the same fallback an unrelated identity-request failure
// already gets) instead of an unhandled exception inside the mount effect.
function resolveGuestIdentity(client: PlatformApiClient): Promise<GuestIdentityResult> {
  const storage = createWindowLocalStorageAdapter();
  return storage ? client.createGuestIdentity({ storage }) : Promise.resolve({ ok: false, error: networkError() });
}

// createGuestIdentity() caches a guest id in localStorage with no server-side revalidation -- if
// the backend later deletes that guest, accept() 404s with isHandoffGuestIdentityInvalid()
// forever for that stale id. Clears it so the next resolveGuestIdentity() call mints a fresh one
// instead of resending the same id that can never succeed.
async function clearStaleGuestIdentity(): Promise<void> {
  try {
    await createWindowLocalStorageAdapter()?.remove(DEFAULT_GUEST_STORAGE_KEY);
  } catch {
    // Storage-denied sandboxes have nothing persisted to clear anyway.
  }
}

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
  // Distinct from `guestId === undefined`: that also covers "not resolved yet," which never
  // reaches the consent view (resolved alongside the preview fetch below, before Accept/Decline
  // can render at all). This tracks a *failed* resolution specifically, so Accept can be kept
  // unavailable instead of silently sending no guest_id -- which the backend's
  // HandoffService.accept() would attribute to the handoff's creator, not the person accepting.
  const [guestIdentityUnresolved, setGuestIdentityUnresolved] = useState(false);

  // The backend attributes an accept's quota to `guest_id` if given, falling back to the
  // handoff's original creator otherwise -- so the person actually clicking Accept needs their
  // own guest identity, not the creator's. Resolved alongside the preview fetch (not after) so
  // Accept/Decline never render before guestId has settled -- otherwise a click that races the
  // identity call would silently fall back to creator-attribution again.
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getHandoff(client, handoffToken, { signal: controller.signal }),
      // createGuestIdentity() has no signal option (it's single-flight and shared across every
      // caller on this client instance, so one caller cancelling could not cancel the others) --
      // a fast unmount/token change leaves this POST running in the background for a discarded
      // result, same as any other fire-and-forget identity call in ce-kit today.
      resolveGuestIdentity(client),
    ]).then(([previewResult, guestResult]) => {
      if (controller.signal.aborted) {
        return;
      }
      setGuestId(guestResult.ok ? guestResult.value.guestId : undefined);
      setGuestIdentityUnresolved(!guestResult.ok);
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
  function showRetryableActionError(): void {
    setState((prev) =>
      prev.kind === "consent" ? { ...prev, pending: null, actionError: "That action could not be completed. Please try again." } : prev,
    );
  }

  async function resolveActionError(error: PlatformApiError): Promise<void> {
    if (isHandoffGuestIdentityInvalid(error)) {
      // Deterministic and permanent for the current guestId (the record stays non-terminal, so
      // refetching would just return the same actionable preview) -- clear the stale persisted id
      // and resolve a fresh one so a retry can actually succeed instead of 404ing forever.
      await clearStaleGuestIdentity();
      const fresh = await resolveGuestIdentity(client);
      setGuestId(fresh.ok ? fresh.value.guestId : undefined);
      setGuestIdentityUnresolved(!fresh.ok);
      showRetryableActionError();
      return;
    }
    if (!isHandoffActionRefetchable(error)) {
      showRetryableActionError();
      return;
    }
    const refetched = await getHandoff(client, handoffToken);
    setState(viewStateFromResult(refetched));
  }

  async function runAction(
    kind: "accept" | "decline",
    mutate: () => Promise<PlatformApiResult<HandoffPreview>>,
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
          <button type="button" onClick={handleAccept} disabled={state.pending !== null || guestIdentityUnresolved}>
            Accept
          </button>
          <button type="button" onClick={handleDecline} disabled={state.pending !== null}>
            Decline
          </button>
          {/* Decline stays available: it needs no guest attribution, unlike Accept. */}
          {guestIdentityUnresolved ? (
            <p role="alert">We couldn't verify your identity. Please reload the page and try again.</p>
          ) : null}
          {state.actionError ? <p role="alert">{state.actionError}</p> : null}
        </>
      ) : null}
    </main>
  );
}
