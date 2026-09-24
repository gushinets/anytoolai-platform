"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Button, Card, Toast } from "@anytoolai/shared-ui";
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
  type HandoffPreview,
  type HandoffStatus,
  type PlatformApiClient,
  type PlatformApiError,
  type PlatformApiResult,
} from "@anytoolai/ce-kit";
import styles from "./HandoffConsent.module.css";

export type HandoffConsentProps = {
  client: PlatformApiClient;
  handoffToken: string;
};

// A `Record<HandoffStatus, boolean>` literal, not a hand-written `Set` -- this fails to typecheck
// if `HandoffStatus` gains or loses a member and this map isn't updated to classify it, so a new
// terminal status can't silently fall through `isTerminalHandoffStatus()` as non-terminal the way
// it could with `ReadonlySet<HandoffStatus>.has()` (any subset of the union typechecks there).
const HANDOFF_STATUS_IS_TERMINAL: Record<HandoffStatus, boolean> = {
  created: false,
  viewed: false,
  accepted: true,
  declined: true,
  consumed: true,
  expired: true,
  failed: true,
};

// User-facing copy for the wire enum. Exhaustive over HandoffStatus so a new status fails typecheck
// here instead of leaking its raw value into the UI. `consumed` means the accepted handoff already
// created its target session, which is one "Accepted" outcome from the user's side.
const HANDOFF_STATUS_LABEL: Record<HandoffStatus, string> = {
  created: "Waiting for your decision",
  viewed: "Waiting for your decision",
  accepted: "Accepted",
  consumed: "Accepted",
  declined: "Declined",
  expired: "Expired",
  failed: "Failed",
};

function formatExpiry(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function isTerminalHandoffStatus(status: HandoffStatus): boolean {
  return HANDOFF_STATUS_IS_TERMINAL[status];
}

type ViewState =
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "safe-error" }
  | { kind: "consent"; preview: HandoffPreview; pending: "accept" | "decline" | null; actionError: string | null }
  | { kind: "terminal"; preview: HandoffPreview };

function stateForPreview(preview: HandoffPreview): ViewState {
  return isTerminalHandoffStatus(preview.status)
    ? { kind: "terminal", preview }
    : { kind: "consent", preview, pending: null, actionError: null };
}

function viewStateFromResult(result: PlatformApiResult<HandoffPreview>): ViewState {
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
  // Fallback storage for guestStorage/refreshGuestIdentity() when window.localStorage itself isn't
  // available -- lazily created once per component instance (stable across re-renders and across a
  // self-heal retry within the same mount), not module-level, so it doesn't leak a minted guest id
  // across remounts/tests the way a module singleton would.
  const [ephemeralGuestStorage] = useState<AsyncStorage>(() => createInMemoryAsyncStorage());
  // Which backend to persist the guest id in, decided once at mount and reused for every storage
  // operation for this component's whole lifetime -- resolving it fresh on each call (as a prior
  // version of this component did, once in the mount effect and again in resolveActionError) risks
  // the two calls disagreeing if localStorage's availability changes in between (e.g. a Storage
  // Access API grant lands mid-session), which would split a stale/fresh guest id across two
  // different storage backends instead of ever colocating them.
  const [guestStorage] = useState<AsyncStorage>(() => createWindowLocalStorageAdapter() ?? ephemeralGuestStorage);
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
      client.createGuestIdentity({ storage: guestStorage }),
    ]).then(
      ([previewResult, guestResult]) => {
        if (controller.signal.aborted) {
          return;
        }
        setGuestId(guestResult.ok ? guestResult.value.guestId : undefined);
        setState(viewStateFromResult(previewResult));
      },
      () => {
        // getHandoff()/createGuestIdentity() never reject today, but a synchronous throw before
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
  }, [client, handoffToken, guestStorage, retryToken]);

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
      const fresh = await refreshGuestIdentity(client, guestStorage, {
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
    try {
      const result = await mutate();
      if (result.ok) {
        setState(stateForPreview(result.value));
      } else {
        await resolveActionError(kind, result.error);
      }
    } catch {
      // mutate()/resolveActionError() should never actually reject, but a rejection must not
      // strand `pending` forever with both buttons permanently disabled and no way to retry --
      // same reasoning as the mount effect's own rejection handler above.
      showRetryableActionError();
    }
  }

  function handleAccept(): void {
    // runAction() already catches every rejection internally (see its own try/catch above), so
    // there's nothing left for a caller to await -- explicitly discard so `onClick` (which expects
    // a void-returning handler) doesn't see this as an unhandled floating promise.
    void runAction("accept", () => acceptHandoff(client, handoffToken, { guestId }));
  }

  function handleDecline(): void {
    void runAction("decline", () => declineHandoff(client, handoffToken));
  }

  function retryAfterSafeError() {
    setState({ kind: "loading" });
    setRetryToken((n) => n + 1);
  }

  if (state.kind === "loading") {
    return (
      <HandoffShell>
        <p role="status">Loading handoff…</p>
      </HandoffShell>
    );
  }
  if (state.kind === "not-found") {
    return (
      <HandoffShell>
        <Toast variant="error">This handoff link is not valid.</Toast>
      </HandoffShell>
    );
  }
  if (state.kind === "safe-error") {
    return (
      <HandoffShell>
        <Toast variant="error">Something went wrong loading this handoff. Please try again.</Toast>
        <Button variant="secondary" onClick={retryAfterSafeError}>
          Try again
        </Button>
      </HandoffShell>
    );
  }

  const { preview } = state;
  return (
    <HandoffShell>
      <dl className={styles.details}>
        <dt>From</dt>
        <dd>{preview.sourceProductDisplayName}</dd>
        <dt>To</dt>
        <dd>{preview.targetProductDisplayName}</dd>
        <dt>Expires</dt>
        <dd>
          <time dateTime={preview.expiresAt}>{formatExpiry(preview.expiresAt)}</time>
        </dd>
        <dt>Status</dt>
        <dd>{HANDOFF_STATUS_LABEL[preview.status]}</dd>
        {Object.entries(preview.preview).map(([key, value]) => (
          <div key={key} className={styles.entry}>
            <dt>{key}</dt>
            <dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd>
          </div>
        ))}
      </dl>
      {state.kind === "consent" ? (
        <>
          <div className={styles.actions}>
            <Button
              onClick={handleAccept}
              loading={state.pending === "accept"}
              disabled={state.pending !== null || guestId === undefined}
            >
              Accept
            </Button>
            <Button
              variant="secondary"
              onClick={handleDecline}
              loading={state.pending === "decline"}
              disabled={state.pending !== null}
            >
              Decline
            </Button>
          </div>
          {/* The spinner is decorative (see Spinner), so the in-flight state is also announced. */}
          {state.pending ? (
            <p role="status" className={styles.status}>
              {state.pending === "accept" ? "Accepting…" : "Declining…"}
            </p>
          ) : null}
          {/* Decline stays available: it needs no guest attribution, unlike Accept. */}
          {guestId === undefined ? (
            <Toast variant="error">We couldn't verify your identity. Please reload the page and try again.</Toast>
          ) : null}
          {state.actionError ? <Toast variant="error">{state.actionError}</Toast> : null}
        </>
      ) : null}
    </HandoffShell>
  );
}

function HandoffShell({ children }: { children: ReactNode }) {
  return (
    <main className={`page-container ${styles.page}`}>
      <Card className={styles.card}>
        <h1 className={styles.title}>Review handoff</h1>
        {children}
      </Card>
    </main>
  );
}
