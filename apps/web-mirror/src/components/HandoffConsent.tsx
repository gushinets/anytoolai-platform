"use client";

import { useEffect, useState } from "react";
import {
  acceptHandoff,
  createInMemoryAsyncStorage,
  createWindowLocalStorageAdapter,
  declineHandoff,
  getHandoff,
  isHandoffActionRefetchable,
  isHandoffGuestIdentityInvalid,
  isHandoffNotFound,
  refreshGuestIdentity,
  type AsyncStorage,
  type GuestIdentityResult,
  type HandoffPreview,
  type PlatformApiClient,
  type PlatformApiError,
  type PlatformApiResult,
} from "@anytoolai/ce-kit";

// createWindowLocalStorageAdapter() already guards against window.localStorage itself throwing
// synchronously (privacy-hardened browsers, storage-denied sandboxed iframes) -- falls back to
// `fallbackStorage` (an in-memory adapter scoped to this component instance) in that case, so lack
// of persistent storage never prevents establishing an acceptor identity for this page. The id
// just won't survive a reload/remount the way a real localStorage one would. Resolved once per
// call site and reused for every storage operation within it, so a mid-call change in
// localStorage's availability can't split one logical operation across two different backends.
function activeGuestStorage(fallbackStorage: AsyncStorage): AsyncStorage {
  return createWindowLocalStorageAdapter() ?? fallbackStorage;
}

function resolveGuestIdentity(client: PlatformApiClient, storage: AsyncStorage): Promise<GuestIdentityResult> {
  return client.createGuestIdentity({ storage });
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
  // `guestId === undefined` doubles as "identity resolution failed": by the time the consent view
  // can render at all, resolution has already settled (below), so there's no separate "still
  // resolving" state left to distinguish it from. Accept is kept unavailable in that case --
  // sending no guest_id would let the backend's HandoffService.accept() attribute the target
  // session/quota to the handoff's creator instead of the person actually accepting.
  const [guestId, setGuestId] = useState<string | undefined>(undefined);
  // Fallback storage for resolveGuestIdentity()/clearStaleGuestIdentity() when window.localStorage
  // itself isn't available -- lazily created once per component instance (stable across
  // re-renders and across a self-heal retry within the same mount), not module-level, so it
  // doesn't leak a minted guest id across remounts/tests the way a module singleton would.
  const [ephemeralGuestStorage] = useState<AsyncStorage>(() => createInMemoryAsyncStorage());
  // Bumped to force the mount effect below to re-run on demand (e.g. a "Try again" click from the
  // safe-error view) without duplicating its fetch logic in a second function.
  const [retryToken, setRetryToken] = useState(0);

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
      resolveGuestIdentity(client, activeGuestStorage(ephemeralGuestStorage)),
    ]).then(
      ([previewResult, guestResult]) => {
        if (controller.signal.aborted) {
          return;
        }
        setGuestId(guestResult.ok ? guestResult.value.guestId : undefined);
        setState(viewStateFromResult(previewResult));
      },
      () => {
        // getHandoff()/resolveGuestIdentity() never reject today, but a synchronous throw before
        // either promise resolves (or a future change to either) must not strand this view on
        // "Loading handoff..." forever with no way out.
        if (!controller.signal.aborted) {
          setState({ kind: "safe-error" });
        }
      },
    );
    return () => {
      controller.abort();
    };
  }, [client, handoffToken, ephemeralGuestStorage, retryToken]);

  // A stale accept/decline can race an already-terminal token (expired, already accepted/declined,
  // or a failed target execution). Rather than retry the mutation, refetch the authoritative
  // preview via getHandoff() and render whatever terminal state it reports -- this is what makes a
  // consumed token unreplayable from the client's side: the backend's current state always wins.
  function showRetryableActionError(): void {
    setState((prev) =>
      prev.kind === "consent" ? { ...prev, pending: null, actionError: "That action could not be completed. Please try again." } : prev,
    );
  }

  // The guest-identity self-heal branch below only ever applies to accept: declineHandoff() never
  // sends guest_id and (per ce-kit's own docs) can only return handoff_expired/handoff_not_actionable
  // -- gating on `kind` keeps that tied to the accept path explicitly, rather than relying on decline
  // simply never triggering it today.
  async function resolveActionError(kind: "accept" | "decline", error: PlatformApiError): Promise<void> {
    if (kind === "accept" && isHandoffGuestIdentityInvalid(error)) {
      // Deterministic and permanent for the current guestId (the record stays non-terminal, so
      // refetching would just return the same actionable preview) -- refreshGuestIdentity() clears
      // the stale persisted id and resolves a fresh one so a retry can actually succeed instead of
      // 404ing forever.
      const fresh = await refreshGuestIdentity(client, activeGuestStorage(ephemeralGuestStorage), {
        fallbackStorage: ephemeralGuestStorage,
      });
      setGuestId(fresh.ok ? fresh.value.guestId : undefined);
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
      await resolveActionError(kind, result.error);
    }
  }

  function handleAccept() {
    return runAction("accept", () => acceptHandoff(client, handoffToken, { guestId }));
  }

  function handleDecline() {
    return runAction("decline", () => declineHandoff(client, handoffToken));
  }

  function retryAfterSafeError() {
    setState({ kind: "loading" });
    setRetryToken((n) => n + 1);
  }

  if (state.kind === "loading") {
    return <p role="status">Loading handoff…</p>;
  }
  if (state.kind === "not-found") {
    return <p role="alert">This handoff link is not valid.</p>;
  }
  if (state.kind === "safe-error") {
    return (
      <>
        <p role="alert">Something went wrong loading this handoff. Please try again.</p>
        <button type="button" onClick={retryAfterSafeError}>
          Try again
        </button>
      </>
    );
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
          <button type="button" onClick={handleAccept} disabled={state.pending !== null || guestId === undefined}>
            Accept
          </button>
          <button type="button" onClick={handleDecline} disabled={state.pending !== null}>
            Decline
          </button>
          {/* Decline stays available: it needs no guest attribution, unlike Accept. */}
          {guestId === undefined ? (
            <p role="alert">We couldn't verify your identity. Please reload the page and try again.</p>
          ) : null}
          {state.actionError ? <p role="alert">{state.actionError}</p> : null}
        </>
      ) : null}
    </main>
  );
}
