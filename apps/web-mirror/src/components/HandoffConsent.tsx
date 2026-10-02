"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button, Card, Toast } from "@anytoolai/shared-ui";
import {
  acceptHandoff,
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
import { productAttachPath } from "../lib/hostUrls";
import { rememberAttachSession } from "../products/runtime/attachSession";
import { getClientStorage } from "../products/runtime/clientStorage";
import { useIsomorphicLayoutEffect } from "../lib/useIsomorphicLayoutEffect";
import { LanguageSwitcher, useHostT, useLocale, useProductT, type Locale } from "../i18n";
import styles from "./HandoffConsent.module.css";

export type HandoffConsentProps = {
  client: PlatformApiClient;
  handoffToken: string;
  /** Whether the web host can attach the accepted handoff's target scenario, so it redirects only to
   * a page that can show that session (the route supplies it; this component must not import the
   * product registry). */
  canOpenTarget?: (productId: string, scenarioId: string) => boolean;
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

// Message key (`status.*`) for the wire enum. Exhaustive over HandoffStatus so a new status fails
// typecheck here instead of leaking its raw value into the UI. `consumed` means the accepted handoff
// already created its target session, which is one "Accepted" outcome from the user's side.
const HANDOFF_STATUS_KEY: Record<HandoffStatus, "waiting" | "accepted" | "declined" | "expired" | "failed"> = {
  created: "waiting",
  viewed: "waiting",
  accepted: "accepted",
  consumed: "accepted",
  declined: "declined",
  expired: "expired",
  failed: "failed",
};

function formatExpiry(iso: string, locale: Locale): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

function isTerminalHandoffStatus(status: HandoffStatus): boolean {
  return HANDOFF_STATUS_IS_TERMINAL[status];
}

type ViewState =
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "safe-error" }
  | { kind: "consent"; preview: HandoffPreview; pending: "accept" | "decline" | null; actionFailed: boolean }
  | { kind: "terminal"; preview: HandoffPreview };

function stateForPreview(preview: HandoffPreview): ViewState {
  return isTerminalHandoffStatus(preview.status)
    ? { kind: "terminal", preview }
    : { kind: "consent", preview, pending: null, actionFailed: false };
}

function viewStateFromResult(result: PlatformApiResult<HandoffPreview>): ViewState {
  if (!result.ok) {
    return isHandoffNotFound(result.error) ? { kind: "not-found" } : { kind: "safe-error" };
  }
  return stateForPreview(result.value);
}

function isAlreadyAccepted(error: PlatformApiError): boolean {
  return error.type === "backend_error" && error.code === "handoff_already_accepted";
}

/** An Accept that may have gone through whose answer was lost or unreadable (transport failure, timeout, a
 * 2xx body that is not a preview): only the authoritative preview says whether it queued (and charged) a target. */
function isAmbiguousAcceptOutcome(error: PlatformApiError): boolean {
  return error.type === "network_error" || error.type === "timeout" || error.type === "invalid_response";
}

/** The target session of an accepted/consumed preview, if the host can open it; null otherwise. The one
 * answer to "is there a queued target we can reach", used to open it, to remember it and to offer it. */
function acceptedTargetSessionId(
  preview: HandoffPreview,
  canOpenTarget: HandoffConsentProps["canOpenTarget"],
): string | null {
  const accepted = preview.status === "accepted" || preview.status === "consumed";
  // `||`, not `??`: an empty id is no id (it would open the target page with nothing to attach).
  return accepted && canOpenTarget?.(preview.targetProductId, preview.targetScenarioId) === true
    ? preview.targetScenarioSessionId || null
    : null;
}

const KNOWN_PREVIEW_FIELDS = ["summary", "missing_fields"] as const;

function isKnownPreviewField(key: string): key is (typeof KNOWN_PREVIEW_FIELDS)[number] {
  return (KNOWN_PREVIEW_FIELDS as readonly string[]).includes(key);
}

/** Strings as sent; a list of strings as a comma-separated line; anything else as opaque JSON. */
function formatPreviewValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value.join(", ") : JSON.stringify(value);
}

/**
 * State machine for the backend-owned handoff consent page. Renders only the fields the backend
 * safe preview carries -- no provider/model, prompt, or raw artifact data ever reaches this
 * component. `preview.preview` is a bounded, config-mapped `dict[str, Any]` on the wire, so it is
 * always rendered as opaque key/value pairs, never by assuming specific keys.
 */
export function HandoffConsent({ client, handoffToken, canOpenTarget }: HandoffConsentProps) {
  const t = useProductT();
  const th = useHostT();
  const { locale } = useLocale();
  const router = useRouter();
  // Not tied to the mount effect's AbortController (it also guards other work); a plain "still on this
  // page" flag, set again on a StrictMode effect replay.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  // `guestId === undefined` doubles as "identity resolution failed": by the time the consent view
  // can render at all, resolution has already settled (below), so there's no separate "still
  // resolving" state left to distinguish it from. Accept is kept unavailable in that case --
  // sending no guest_id would let the backend's HandoffService.accept() attribute the target
  // session/quota to the handoff's creator instead of the person actually accepting.
  const [guestId, setGuestId] = useState<string | undefined>(undefined);
  // The same per-client storage the product pages use (`getClientStorage`: localStorage when usable,
  // else one in-memory store per client), so the guest that accepts here is the guest the target
  // product page -- reached by a client-side redirect on the same client -- resolves. It is also
  // decided once, so every storage operation for this mount uses one backend.
  const [guestStorage] = useState<AsyncStorage>(() => getClientStorage(client));
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
      prev.kind === "consent" ? { ...prev, pending: null, actionFailed: true } : prev,
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
      const fresh = await refreshGuestIdentity(client, guestStorage);
      if (!mountedRef.current) {
        return;
      }
      setGuestId(fresh.ok ? fresh.value.guestId : undefined);
      showRetryableActionError();
      return;
    }
    if (!isHandoffActionRefetchable(error)) {
      showRetryableActionError();
      return;
    }
    const refetched = await getHandoff(client, handoffToken);
    if (!mountedRef.current) {
      // Left while the refetch was in flight: its answer still names the queued session, so keep it.
      if (kind === "accept" && refetched.ok) {
        rememberAcceptedTarget(refetched.value);
      }
      return;
    }
    setState(viewStateFromResult(refetched));
    // A lost Accept response: the retry gets "already accepted" and this authoritative preview names
    // the target session the first Accept already queued (and charged), so reach it the same way.
    if (kind === "accept" && refetched.ok && (refetched.value.status === "accepted" || refetched.value.status === "consumed")) {
      redirectToAcceptedTarget(refetched.value);
    }
  }

  // Keep the queued session for the target product's next visit (an Accept that settled after the person left).
  function rememberAcceptedTarget(preview: HandoffPreview): void {
    const sessionId = acceptedTargetSessionId(preview, canOpenTarget);
    if (sessionId !== null) {
      rememberAttachSession(preview.targetProductId, sessionId, preview.expiresAt);
    }
  }

  // An accepted handoff has already queued its target session server-side; the ids are redacted once the
  // token's TTL passes, so go to the target product right away, same tab -- but only when the host can
  // attach it (other targets, e.g. an extension, stay on this page's terminal status). Also the explicit
  // "Open result" action.
  function redirectToAcceptedTarget(preview: HandoffPreview): void {
    const sessionId = acceptedTargetSessionId(preview, canOpenTarget);
    if (sessionId !== null) {
      // Remembered with its rank before leaving, so a late response of an OLDER Accept cannot replace it.
      rememberAcceptedTarget(preview);
      router.push(productAttachPath(preview.targetProductId, sessionId));
    }
  }

  async function runAction(
    kind: "accept" | "decline",
    mutate: () => Promise<PlatformApiResult<HandoffPreview>>,
  ) {
    setState((prev) => (prev.kind === "consent" ? { ...prev, pending: kind, actionFailed: false } : prev));
    try {
      const result = await mutate();
      if (!mountedRef.current) {
        // The Accept already happened server-side (and charged the quota) though the person has left this
        // page: keep the session it queued for the target product's next visit, and do not navigate over
        // wherever they went. (Left before any answer arrived, the id is simply unknown.)
        if (result.ok && kind === "accept") {
          rememberAcceptedTarget(result.value);
        } else if (!result.ok && kind === "accept" && (isAlreadyAccepted(result.error) || isAmbiguousAcceptOutcome(result.error))) {
          // "Already accepted" proves the Accept went through (an expired, declined or failed handoff does not),
          // and a lost or unreadable answer may hide one: one read of the authoritative preview names the
          // session it queued, if any. Nothing else continues (no state, no navigation).
          void getHandoff(client, handoffToken).then((refetched) => {
            if (refetched.ok) {
              rememberAcceptedTarget(refetched.value);
            }
          });
        }
        return;
      }
      if (result.ok) {
        setState(stateForPreview(result.value));
        if (kind === "accept") {
          redirectToAcceptedTarget(result.value);
        }
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
        <p role="status">{t("loading")}</p>
      </HandoffShell>
    );
  }
  if (state.kind === "not-found") {
    return (
      <HandoffShell>
        <Toast variant="error">{t("notFound")}</Toast>
      </HandoffShell>
    );
  }
  if (state.kind === "safe-error") {
    return (
      <HandoffShell>
        <Toast variant="error">{t("loadFailed")}</Toast>
        <Button variant="secondary" onClick={retryAfterSafeError}>
          {t("retry")}
        </Button>
      </HandoffShell>
    );
  }

  const { preview } = state;
  return (
    <HandoffShell>
      <dl className={styles.details}>
        <dt>{t("fields.from")}</dt>
        <dd>{preview.sourceProductDisplayName}</dd>
        <dt>{t("fields.to")}</dt>
        <dd>{preview.targetProductDisplayName}</dd>
        <dt>{t("fields.expires")}</dt>
        <dd>
          <time dateTime={preview.expiresAt}>{formatExpiry(preview.expiresAt, locale)}</time>
        </dd>
        <dt>{t("fields.status")}</dt>
        {/* One element in both the consent and the terminal view, so when an action settles its text
            change is announced: the pending line below disappears with the consent controls and the
            focused button unmounts, which would otherwise leave no sign that the outcome arrived. */}
        <dd aria-live="polite">{t(`status.${HANDOFF_STATUS_KEY[preview.status]}`)}</dd>
        {Object.entries(preview.preview).map(([key, value]) => (
          <div key={key} className={styles.entry}>
            <dt>{isKnownPreviewField(key) ? t(`previewFields.${key}`) : key}</dt>
            <dd>{formatPreviewValue(value)}</dd>
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
              {t("accept")}
            </Button>
            <Button
              variant="secondary"
              onClick={handleDecline}
              loading={state.pending === "decline"}
              disabled={state.pending !== null}
            >
              {t("decline")}
            </Button>
          </div>
          {/* The spinner is decorative (see Spinner), so the in-flight state is also announced. */}
          {state.pending ? (
            <p role="status" className={styles.status}>
              {state.pending === "accept" ? t("accepting") : t("declining")}
            </p>
          ) : null}
          {/* Decline stays available: it needs no guest attribution, unlike Accept. */}
          {guestId === undefined ? (
            <Toast variant="error">{th("identityUnavailable")}</Toast>
          ) : null}
          {state.actionFailed ? <Toast variant="error">{t("actionFailed")}</Toast> : null}
        </>
      ) : null}
      {/* A spent token still names the target session the accept queued (and charged) until its TTL. If
          the Accept response was lost and the person reloaded instead of retrying, this is the only way
          to it -- an explicit action, not an automatic jump, because the page may be opened later just to
          look. */}
      {state.kind === "terminal" && acceptedTargetSessionId(preview, canOpenTarget) !== null ? (
        <div className={styles.actions}>
          <Button onClick={() => redirectToAcceptedTarget(preview)}>{t("openResult")}</Button>
        </div>
      ) : null}
    </HandoffShell>
  );
}

function HandoffShell({ children }: { children: ReactNode }) {
  const t = useProductT();
  const title = t("title");
  // The server layout can only give the English fallback title (it does not know the user's
  // language), so the tab title follows the active locale here, like the page itself. Next streams
  // the route's own title in after hydration, which would replace one set only once, so the title
  // is re-applied whenever <head> changes it back. Layout-effect timing, like `<html lang>` in
  // LocaleProvider, so a language switch changes the page, `lang` and the tab title together.
  useIsomorphicLayoutEffect(() => {
    const full = `${title} · AnytoolAI`;
    const apply = () => {
      if (document.title !== full) {
        document.title = full;
      }
    };
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(document.head, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [title]);
  return (
    <main className={`page-container ${styles.page}`}>
      <Card className={styles.card}>
        <header className={styles.header}>
          <h1 className={styles.title}>{title}</h1>
          <LanguageSwitcher />
        </header>
        {children}
      </Card>
    </main>
  );
}
