"use client";

import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Button, Card } from "@anytoolai/shared-ui";
import {
  copyResultAndRecordActivation,
  getQuota,
  getResult,
  getRuntimeConfig,
  isGuestIdentityNotFound,
  isQuotaExhausted,
  isResultNotFound,
  isResultUnavailable,
  pollScenarioSession,
  prepareScenarioStart,
  refreshGuestIdentity,
  type AsyncStorage,
  type PlatformApiClient,
  type PreparedScenarioStart,
  type QuotaState,
} from "@anytoolai/ce-kit";
import { ErrorState } from "../../components/ErrorState";
import { useHostT, useProductT } from "../../i18n";
import { getClientStorage } from "./clientStorage";
import type { FieldError } from "./fieldValidation";
import { assertNever, type ProductDefinition, type ProductRunEvent } from "./productDefinition";
import styles from "./ProductRunPage.module.css";

export type ProductRunPageProps<V extends Record<string, unknown>, R> = {
  definition: ProductDefinition<V, R>;
  client: PlatformApiClient;
  /**
   * Generic event integration point (ANY-453's "The foundation exposes callbacks/integration
   * points and tests them with injected handlers; product integration verifies the real event
   * path after both prerequisites are ready" -- ANY-17 owns that real event path). No real
   * dispatch is wired here; this only exposes and tests the callback contract.
   */
  onEvent?: (event: ProductRunEvent) => void;
  /**
   * Fires whenever this mount's own submitting/running state changes -- code review finding: a
   * multi-mode product (Client Update Writer) that remounts `ProductRunPage` on every mode switch
   * (`key={modeId}`) could switch mode mid-run, abandoning an already-accepted, quota-consuming
   * scenario run: the remount's cleanup aborts the poll/result fetch, but the backend keeps running
   * it and the result is lost to the UI. Lets a multi-mode caller disable its own mode switch while
   * `true`, without this shared runtime needing to know what "mode switching" means for any
   * particular product. Single-mode products (ProposalAI) have nothing to gate on this and can
   * ignore it.
   */
  onBusyChange?: (busy: boolean) => void;
  /**
   * Scopes the `product_viewed`/`form_started` once-per-visit dedupe below to one real page visit
   * -- code review finding: keying that dedupe by `(client, productId)` alone meant it lived for
   * as long as the `client` instance did, not for one visit. `apps/web-mirror/src/app/products/
   * [productId]/page.tsx` uses the page-load-wide `getPlatformApiClient()`, so a client-side
   * navigation between products (none exists in the app today, but the client would survive one) and
   * a genuine A -> B -> A revisit share that same client -- without a
   * visit-scoped key, the second visit to A silently emitted neither event. The route wrapper
   * mints a fresh `visitId` per landing on a product (see its own comment); a multi-mode product's
   * several `ProductRunPage` mounts (one per mode switch) all receive the *same* `visitId` from
   * their shared parent, so switching modes still doesn't refire either event. Falls back to
   * `productId` alone when omitted, matching the previous (lifetime-of-client-scoped) behavior --
   * every existing test constructs `ProductRunPage` directly without a route wrapper.
   */
  visitId?: string;
};

/**
 * Invokes a caller-supplied event handler defensively: neither a synchronous throw nor an async
 * handler's later rejection (TS's `() => void` return type structurally accepts `() => Promise<void>`,
 * so an `async` handler is a legal `onEvent`) may break the product page (ANY-453: "keep analytics
 * failure non-blocking"). `Promise.resolve(...)` correctly adopts a genuine thenable and just
 * wraps a plain sync return value otherwise, so no manual `.then`-sniffing is needed.
 */
function emitEvent(handler: ((event: ProductRunEvent) => void) | undefined, event: ProductRunEvent): void {
  try {
    Promise.resolve(handler?.(event)).catch(_noop);
  } catch {
    // handler threw synchronously -- nothing to attach a rejection handler to.
  }
}

/**
 * A per-(client, key) cache that only remembers a *successful* (`ok: true`) resolution --
 * code review finding: an earlier version cached the raw pending promise unconditionally, so a
 * single transient network failure got remembered forever (`getRuntimeConfig`/`getQuota` resolve
 * `{ok: false}` on failure rather than rejecting, so nothing ever naturally evicted it). A
 * `{ok: false}` result is left uncached, so the next caller retries instead of replaying the same
 * dead failure until a full page reload.
 */
function cacheSuccessOnly<T extends { ok: boolean }>(
  cache: WeakMap<PlatformApiClient, Map<string, Promise<T>>>,
  client: PlatformApiClient,
  key: string,
  fetch: () => Promise<T>,
): Promise<T> {
  let byKey = cache.get(client);
  if (!byKey) {
    byKey = new Map();
    cache.set(client, byKey);
  }
  const cached = byKey.get(key);
  if (cached) {
    return cached;
  }
  const pending = fetch();
  byKey.set(key, pending);
  const settledByKey = byKey;
  function evictIfCurrent() {
    if (settledByKey.get(key) === pending) {
      settledByKey.delete(key);
    }
  }
  // Code review finding: `fetch` is only documented to resolve `{ok: false}` on failure, not to
  // reject -- but nothing enforces that (a thrown error inside it, e.g. from response parsing,
  // still rejects this `async function`'s promise). Without a rejection handler here, that promise
  // stayed cached forever for `(client, key)`, defeating this function's whole purpose; evicting
  // on rejection too, not just on `{ok: false}`, closes that gap. The caller's own subscription to
  // `pending` (returned below) still sees the rejection independently -- this only stops it being
  // replayed to the next caller.
  void pending.then((result) => {
    if (!result.ok) {
      evictIfCurrent();
    }
  }, evictIfCurrent);
  return pending;
}

// Runtime config is immutable per (client, productId) for the lifetime of a page load -- caching
// it here means a product that mounts several ProductRunPage instances for the same productId in
// sequence (e.g. Client Update Writer's mode switcher, which remounts on every mode change since
// each mode's form values have an incompatible shape) doesn't re-fetch identical data on every
// switch. Keyed by the client instance (not a bare module-level cache) so distinct clients --
// different tests, or a real app with more than one client -- never share entries.
//
// Guest identity and quota are deliberately NOT cached this way: identity already caches itself
// via guestStorage, and quota genuinely changes over the page's lifetime as the guest consumes
// it -- a code review finding caught a first attempt at caching quota the same way this file
// caches runtime config, which went stale the instant a run actually consumed quota (never
// invalidated after a successful start), didn't key by guestId (a guest-identity self-heal could
// read a stale/wrong guest's cached result), and didn't dedupe concurrent calls the way this
// function does. Quota is cheap, advisory, and re-fetched on every mount instead.
const runtimeConfigCache = new WeakMap<PlatformApiClient, Map<string, ReturnType<typeof getRuntimeConfig>>>();

function getCachedRuntimeConfig(client: PlatformApiClient, productId: string) {
  return cacheSuccessOnly(runtimeConfigCache, client, productId, () => getRuntimeConfig(client, productId));
}

/**
 * Tracks which top-of-funnel events have already fired for a given (client, scope key) -- not a
 * per-component-instance `useRef`, because a product whose page remounts `ProductRunPage` for the
 * same product (Client Update Writer's mode switcher, via `key={modeId}`) would otherwise refire
 * `product_viewed`/`form_started` once per mode visited instead of once per real visit to that
 * product (code review finding). Survives across those remounts the same way `getCachedRuntimeConfig`
 * does, by living outside the component instance; StrictMode's mount -> cleanup -> remount replay
 * still only fires each event once, same as before.
 *
 * The scope key is `visitId ?? productId` (see `ProductRunPageProps.visitId`'s own docstring):
 * a bare `productId` key alone (an earlier version of this cache) lived for as long as the
 * `client` instance did, not for one visit -- `apps/web-mirror/src/app/products/[productId]/
 * page.tsx` uses the page-load-wide `getPlatformApiClient()`, so a client-side navigation between
 * products (none exists in the app today, but the client would survive one) shares that same client
 * and a genuine A -> B -> A revisit silently
 * undercounted the second visit to A (code review finding). `visitId` closes that gap for the
 * real production route; direct `ProductRunPage` construction (every current test) has no route
 * wrapper to mint one and keeps the old, simpler `productId`-only scoping.
 */
const firedEventTypesCache = new WeakMap<PlatformApiClient, Map<string, Set<string>>>();

function hasEventFired(client: PlatformApiClient, scopeKey: string, eventType: string): boolean {
  return firedEventTypesCache.get(client)?.get(scopeKey)?.has(eventType) ?? false;
}

function markEventFired(client: PlatformApiClient, scopeKey: string, eventType: string): void {
  let byScopeKey = firedEventTypesCache.get(client);
  if (!byScopeKey) {
    byScopeKey = new Map();
    firedEventTypesCache.set(client, byScopeKey);
  }
  let fired = byScopeKey.get(scopeKey);
  if (!fired) {
    fired = new Set();
    byScopeKey.set(scopeKey, fired);
  }
  fired.add(eventType);
}

// `useLayoutEffect` is a no-op-with-a-warning during SSR (no DOM) -- Next.js still does an
// initial server render of "use client" components -- so this falls back to `useEffect` there and
// only upgrades to the synchronous, pre-paint timing in an actual browser (or jsdom, which defines
// `window`). Code review finding: `onBusyChange` firing from a plain `useEffect` runs *after* the
// browser could already have painted the settled result (Copy button visible) while the parent's
// own mirrored `busy` state was still stale, so a mode-switch click landing in that window was
// silently dropped -- `useLayoutEffect` flushes the whole child-fires-effect -> parent-setState ->
// parent-re-renders cascade synchronously, before that intermediate state is ever observable.
const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

function shallowEqualValues<V extends Record<string, unknown>>(a: V, b: V): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => Object.is(a[key], b[key]));
}

type BootState =
  | { kind: "loading" }
  | { kind: "boot-error" }
  | { kind: "ready"; scenarioId: string; frontendId: string };

/** Why a run is retryable. A closed reason -- not finished English prose -- so an error already on
 * screen re-renders in the new language when the UI locale changes (`host.errors.<reason>`). */
type RetryReason = "startFailed" | "timeout" | "connectionLost" | "tryAgain";

type Phase<R> =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; scenarioSessionId: string }
  | { kind: "result"; scenarioSessionId: string; checkpointId: string | null; result: R }
  | { kind: "quota-exhausted" }
  | { kind: "retryable-error"; reason: RetryReason }
  /**
   * The scenario session itself completed successfully (we have a `resultArtifactId`) but the
   * `GET /v1/results/{id}` call failed -- a transient/ambiguous fetch problem, not a backend
   * conclusion about the run. Distinct from "unknown-error": retrying here only re-fetches the
   * same artifact, it never starts a new scenario run (see `fetchResult`/`handleRetryResult`).
   */
  | { kind: "result-fetch-error"; scenarioSessionId: string; resultArtifactId: string; checkpointId: string | null }
  | { kind: "unknown-error" };

/**
 * The shared, product-neutral web product runtime: guest identity + runtime config + advisory
 * quota on mount, the product's own form, an idempotent scenario start, bounded polling, the
 * canonical result handed to the product's renderer, and copy activation via the product's next
 * action. Contains no product meaning and imports no product module -- everything
 * product-specific arrives through `definition` (see `productDefinition.ts`).
 *
 * Extracted from the first real product (ProposalAI) once that product had proven which parts
 * were genuinely product-neutral, per ANY-453's team-lead guidance (docs/exec-plans/active/
 * any-453-shared-web-product-runtime-foundation.md) -- not designed up front.
 */
export function ProductRunPage<V extends Record<string, unknown>, R>({
  definition,
  client,
  onEvent,
  onBusyChange,
  visitId,
}: ProductRunPageProps<V, R>) {
  const { Fields, Result } = definition;
  const th = useHostT();
  const tp = useProductT();
  const title = tp("title");

  // Always-current `onEvent` behind a ref, refreshed after every render. Used by every
  // emitEvent() call site below, not just the mount effect: `handleSubmit`/`handleRetry`/
  // `updateField` are genuinely synchronous DOM-event-handler closures where using the `onEvent`
  // prop directly would already be safe, but `runPoll` (a multi-second async continuation) and
  // `handleCopy` (invoked from the product renderer's own copy-button handler, itself async) are
  // not -- either can run after a re-render has already handed the parent a new
  // `onEvent` identity, and a closure captured before that await would fire the stale one. Using
  // the ref uniformly, rather than trying to classify each call site as "safe," avoids
  // re-introducing this exact bug: an earlier version used `onEvent` directly in `runPoll`.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });
  // Bumped by every fetchResult() call; see that function's own comment for why.
  const resultFetchGenerationRef = useRef(0);
  // True once any concurrent fetchResult() call for the current session has reached a definitive,
  // artifact-deterministic outcome (a usable result, a malformed one, or a permanently-unavailable
  // rejection); reset per session at the top of runPoll(). See fetchResult()'s own comment.
  const resultFetchSettledRef = useRef(false);
  // The scenarioSessionId runPoll() is currently polling/fetching a result for -- set at the top
  // of runPoll(), alongside resultFetchSettledRef's own reset. `controllerRef`'s AbortController
  // lives for the whole component, not per logical run, so a fetchResult() call from an *older*
  // session (still in flight when the user starts a brand new one) never gets aborted on its own;
  // this is what fetchResult() checks to recognize and discard such a call, however it resolves.
  const activeScenarioSessionIdRef = useRef<string | null>(null);

  const [boot, setBoot] = useState<BootState>({ kind: "loading" });
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const [guestId, setGuestId] = useState<string | undefined>(undefined);
  // See `getClientStorage`: one storage per client, so a remount never mints a new guest.
  const [guestStorage] = useState<AsyncStorage>(() => getClientStorage(client));
  // Fresh AbortController created inside the effect itself, not a `useState` singleton: aborts
  // every in-flight read (identity/runtime-config/quota on mount, poll/result while a run is
  // active) on unmount so none of them can call setState after this component is gone. A
  // `useState`-held controller would be the SAME instance across React StrictMode's double-invoke
  // of effects (mount -> cleanup -> remount): that cleanup's abort() would permanently kill the
  // single shared instance before the remount's own effects (or any later user action) ever got
  // to use it, leaving every subsequent request short-circuited by `signal.aborted` forever.
  // Recreating the controller inside the effect gives each invocation, including a StrictMode
  // replay, its own independent, un-aborted controller.
  const controllerRef = useRef<AbortController | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const [values, setValues] = useState<V>(definition.emptyValues);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof V, FieldError>>>({});
  const [phase, setPhase] = useState<Phase<R>>({ kind: "idle" });
  // Holds the one Idempotency-Key-bound handle for the current logical submission (ANY-150): a
  // "Try again" after a retryable failure reuses `.execute()` on this same handle so the backend
  // can collapse a duplicate submit into the original session instead of spending quota twice.
  // Editing any field after a failure makes the next submit build a genuinely new handle instead.
  // Declared before `busy` below, which reads it.
  const [pendingStart, setPendingStart] = useState<{ prepared: PreparedScenarioStart; input: V } | null>(null);
  // Code review finding: `retryable-error` alone isn't a safe-to-remount signal -- both an
  // ambiguous poll failure (timeout/connection loss in `runPoll`, backend may still be running the
  // accepted session) *and* an ambiguous `/start` failure itself (network/timeout/5xx -- the
  // backend may have already accepted the start, created the session, and consumed quota before
  // the response was lost) land here, and both deliberately keep `pendingStart` alive so a retry
  // can reattach via the same Idempotency-Key instead of starting (and charging) a new run. A
  // mode switch remounting this component would destroy that same `pendingStart`, so `pendingStart
  // !== null` -- not a per-phase flag guessing which specific ambiguous case this is -- is the
  // actual thing worth gating on: it's already true in exactly (and only) the cases where
  // abandoning this instance would lose real, uncommitted reattachment state. Two `retryable-error`
  // transitions are genuinely safe and explicitly clear `pendingStart` themselves before landing
  // here: the deterministic guest-identity-not-found self-heal, and (code review finding) any other
  // deterministic `/start` rejection -- see `runStart`'s own comment for why a definite 4xx there
  // means no session/job was ever created, unlike a network failure/timeout/5xx. Also covers the
  // form's own Submit button and fields (below), not just the mode-switch guard -- editing values
  // or resubmitting during any of these ambiguous windows would equally abandon the original
  // Idempotency-Key reattachment path.
  //
  // Code review finding: `result-fetch-error` needs the same "unsafe to abandon" treatment for a
  // different reason -- that phase means the scenario session already completed and consumed its
  // quota unit, and only the follow-up `GET /results/{id}` failed. There's no `pendingStart` to
  // reattach to (a fresh submit was never on the table), but remounting would still destroy the
  // only handle the UI has left on an already-paid-for result (`resultArtifactId`), stranding it
  // just as permanently as abandoning an ambiguous start would. It never renders the form (see the
  // phase switch below), so this has no effect on the Submit button/fields.
  const busy =
    phase.kind === "submitting" ||
    phase.kind === "running" ||
    phase.kind === "result-fetch-error" ||
    (phase.kind === "retryable-error" && pendingStart !== null);
  // Always-current, same reasoning as `onEventRef` above -- `onBusyChange` itself is not a
  // dependency of the effect below (a new identity every render must not re-fire it).
  const onBusyChangeRef = useRef(onBusyChange);
  useEffect(() => {
    onBusyChangeRef.current = onBusyChange;
  });
  useIsomorphicLayoutEffect(() => {
    onBusyChangeRef.current?.(busy);
  }, [busy]);

  const productId = definition.productId;
  const scenarioId = definition.scenarioId;
  // See `ProductRunPageProps.visitId`'s own docstring: falls back to `productId` alone (the old
  // behavior) when no route wrapper supplies a per-visit id.
  const eventScopeKey = visitId ?? productId;
  useEffect(() => {
    // Snapshotted once per effect invocation (including StrictMode's replay), not re-read from
    // controllerRef inside the .then() continuations below: by the time those run, the ref could
    // already point at a newer controller from a later invocation, which would wrongly report
    // "not aborted" for a continuation that belongs to an already-superseded one.
    const controller = controllerRef.current;
    // Deduped via the shared (client, eventScopeKey) cache above, not a per-instance ref --
    // guards both React StrictMode's dev-only double-invoke of effects (mount -> cleanup ->
    // remount) and a Client Update Writer-style mode-switch remount from double-counting this
    // top-of-funnel event. Declared inside this effect (its only caller) rather than at component
    // scope so it doesn't need its own identity in the dependency array below.
    function emitProductViewed(resolvedGuestId: string | undefined) {
      if (hasEventFired(client, eventScopeKey, "product_viewed")) {
        return;
      }
      markEventFired(client, eventScopeKey, "product_viewed");
      emitEvent(onEventRef.current, { type: "product_viewed", guestId: resolvedGuestId });
    }
    Promise.all([getCachedRuntimeConfig(client, productId), client.createGuestIdentity({ storage: guestStorage })]).then(
      ([runtimeResult, guestResult]) => {
        if (controller?.signal.aborted) {
          return;
        }
        const resolvedGuestId = guestResult.ok ? guestResult.value.guestId : undefined;
        setGuestId(resolvedGuestId);
        emitProductViewed(resolvedGuestId);
        if (!runtimeResult.ok) {
          setBoot({ kind: "boot-error" });
          return;
        }
        // Resolved by id, not position: runtime config's `scenarios` array isn't guaranteed to be
        // a singleton (see `ProductDefinition.scenarioId`'s own docstring) or ordered to match
        // this product's meaning.
        const scenario = runtimeResult.value.scenarios.find((candidate) => candidate.scenarioId === scenarioId);
        // No fallback to frontends[0]: that could silently select a disabled frontend or a
        // non-web one, letting a disabled/wrong-type frontend still expose the form/start flow.
        // No enabled web frontend means this product isn't actually available here.
        const frontend = runtimeResult.value.frontends.find(
          (candidate) => candidate.type === "web" && candidate.enabled,
        );
        if (!scenario || !frontend) {
          setBoot({ kind: "boot-error" });
          return;
        }
        setBoot({ kind: "ready", scenarioId: scenario.scenarioId, frontendId: frontend.frontendId });

        if (resolvedGuestId) {
          // Advisory only: shown if it loads in time, never blocks the form from becoming usable.
          // scenarioId is always passed, not just for scenario-dimension policies: per
          // frontend-boundaries.md, a scenario-dimension quota policy *requires* it while a
          // product-wide policy simply "does not require it" (optional, not rejected) -- passing
          // it unconditionally keeps this shared runtime correct for either policy shape without
          // needing to know which one a given product uses.
          getQuota(client, { productId, guestId: resolvedGuestId, scenarioId: scenario.scenarioId }).then((quotaResult) => {
            if (controller?.signal.aborted || !quotaResult.ok) {
              return;
            }
            setQuota(quotaResult.value);
            if (quotaResult.value.exhausted) {
              // Functional update, gated on the phase still being "idle": this advisory GET can
              // resolve after the user has already submitted (or even completed) a run -- an
              // unconditional setPhase() here would clobber "submitting"/"running"/"result" with
              // a stale "quota-exhausted", hiding an active or already-successful run behind it.
              setPhase((prev) => (prev.kind === "idle" ? { kind: "quota-exhausted" } : prev));
            }
          }, _noop);
        }
      },
      () => {
        if (!controller?.signal.aborted) {
          setBoot({ kind: "boot-error" });
          emitProductViewed(undefined);
        }
      },
    );
  }, [client, guestStorage, productId, scenarioId, eventScopeKey]);

  async function runStart(prepared: PreparedScenarioStart) {
    // Snapshotted once: this call's own controller, checked consistently across every await below
    // regardless of which controller (if any) controllerRef points to by the time each resolves.
    const controller = controllerRef.current;
    const result = await prepared.execute(client, { signal: controller?.signal });
    if (controller?.signal.aborted) {
      return;
    }
    if (!result.ok) {
      if (isQuotaExhausted(result.error)) {
        setPhase({ kind: "quota-exhausted" });
        return;
      }
      if (isGuestIdentityNotFound(result.error)) {
        // Deterministic and permanent for the stale guest id -- self-heal so a plain resubmit
        // (not a special "retry" action) can succeed. The stale handle's request body carries the
        // old guest_id, so it can't be reused: clearing it forces a fresh prepareScenarioStart().
        const fresh = await refreshGuestIdentity(client, guestStorage);
        if (controller?.signal.aborted) {
          return;
        }
        setGuestId(fresh.ok ? fresh.value.guestId : undefined);
        setPendingStart(null);
        setPhase({ kind: "retryable-error", reason: "tryAgain" });
        return;
      }
      if (result.error.type === "backend_error" && result.error.status < 500) {
        // Code review finding: a definite 4xx here (`scenario_not_found`, `idempotency_key_conflict`,
        // `scenario_input_invalid`/`scenario_frontend_invalid`, `guest_identity_required`, ...;
        // `quota_exhausted`/`guest_identity_not_found` were already peeled off above) means the
        // backend validated and rejected the request *before* creating a session/job -- unlike a
        // network failure/timeout/5xx, there's nothing ambiguous left to reattach to. Clearing
        // `pendingStart` lets the next submit mint a fresh Idempotency-Key (needed either way for
        // `idempotency_key_conflict`, since replaying the same key would just repeat the same 409
        // forever) and, via `busy`, immediately unblocks the form/mode switch.
        setPendingStart(null);
        setPhase({ kind: "retryable-error", reason: "startFailed" });
        return;
      }
      // Ambiguous, not necessarily a clean rejection: a network failure/timeout/5xx on the start
      // request itself doesn't tell us whether the backend actually accepted it (created the
      // session/job and charged quota) before the response was lost -- `pendingStart` (with its
      // Idempotency-Key) stays exactly as set by the caller, so a retry collapses onto whatever the
      // backend actually did rather than risk a second, quota-consuming start. See `busy`'s own
      // comment for why this is also why a mode switch must stay blocked here.
      setPhase({ kind: "retryable-error", reason: "startFailed" });
      return;
    }
    setPhase({ kind: "running", scenarioSessionId: result.value.scenarioSessionId });
    void runPoll(result.value.scenarioSessionId);
  }

  async function runPoll(scenarioSessionId: string) {
    // Fresh per logical run: this session's result-fetch lifecycle (this call plus any later
    // handleRetryResult() retries against the same artifact) hasn't settled yet, and it's now the
    // one fetchResult() calls are allowed to act for.
    resultFetchSettledRef.current = false;
    activeScenarioSessionIdRef.current = scenarioSessionId;
    const controller = controllerRef.current;
    const polled = await pollScenarioSession(client, scenarioSessionId, { signal: controller?.signal });
    if (controller?.signal.aborted) {
      return;
    }
    if (!polled.result.ok) {
      setPhase({ kind: "retryable-error", reason: polled.reason === "timeout" ? "timeout" : "connectionLost" });
      return;
    }
    if (polled.reason === "timeout") {
      // pollScenarioSession() returning `result.ok: true` together with `reason: "timeout"` means
      // the *last* snapshot it saw was still non-terminal (started/running) when the bounded
      // polling budget ran out -- not a backend conclusion about the run, just this poll giving
      // up early. Treating that as enterUnknownError() (like a genuinely terminal status below)
      // would clear pendingStart and abandon a job that may still be actively running server-side.
      // Ambiguous, so this is retryable-error: its retry reuses the same Idempotency-Key, and the
      // backend collapses that back onto this same session rather than starting a new one --
      // see `busy`'s own comment below for why this stays gated on `pendingStart`, not a
      // per-phase session id.
      setPhase({ kind: "retryable-error", reason: "timeout" });
      return;
    }
    const session = polled.result.value;
    if (session.status !== "completed") {
      // `failed`/`expired` land here as genuinely terminal. `waiting_for_user` does too, since
      // this runtime only supports the single-checkpoint "run to completion, then one
      // post-completion activation" shape (see `ProductDefinition`'s docstring) -- a mid-flow
      // checkpoint needing a product-chosen next action isn't handled yet, deliberately, until a
      // real product needs it.
      enterUnknownError();
      return;
    }
    if (!session.resultArtifactId) {
      enterUnknownError();
      return;
    }
    await fetchResult(scenarioSessionId, session.resultArtifactId, session.currentCheckpointId);
  }

  // Any transition into "unknown-error" means the backend already reached a definitive terminal
  // outcome for that specific session -- reusing the old PreparedScenarioStart/Idempotency-Key
  // would just replay that same dead session forever (the backend collapses a repeated key into
  // the existing session's snapshot, it never starts a new run). Clearing pendingStart right here,
  // at the single place this phase is ever entered, is what guarantees that invariant regardless
  // of *how* the user gets back to a fresh submit: "unknown-error" is grouped with the
  // form-showing phases below (its retry isn't the only path back to the submit button), so
  // invalidating the stale start only inside one specific "Try again" handler previously left the
  // ordinary form Submit button able to silently replay it too.
  function enterUnknownError() {
    setPendingStart(null);
    setPhase({ kind: "unknown-error" });
  }

  // Shared by runPoll and handleRetryResult: the session already completed server-side (we have
  // its resultArtifactId); this only fetches the canonical result for it, and never starts a new
  // scenario run -- see the "result-fetch-error" Phase variant's docstring.
  async function fetchResult(scenarioSessionId: string, resultArtifactId: string, checkpointId: string | null) {
    // handleRetryResult()'s button isn't disabled while a fetch is in flight, so a double-click
    // (or click-during-the-initial-poll-driven-call, in principle) can start a second, overlapping
    // fetchResult() for the same artifact. A per-call generation, checked after the await, stops a
    // *stale* completion from re-showing a superseded transient error -- but generation order
    // (who started last) and resolution order (who finishes last) aren't the same thing, and every
    // concurrent call reads the exact same immutable artifact. So a plain "last-started wins" rule
    // has its own bug: an *older* call's success, resolving after a *newer* call already started,
    // would be discarded outright by that rule, and a subsequent transient failure from the newer
    // call would then be the only thing shown -- clobbering a result that was, in fact, already
    // successfully fetched. `resultFetchSettledRef` fixes this: any definitive, artifact-
    // deterministic outcome (success, permanently-unavailable, or malformed) is applied the moment
    // it arrives, from whichever call got there first, and marks the fetch settled so every other
    // concurrent completion -- of any generation, resolving before or after -- becomes a no-op.
    // Only a genuinely transient/ambiguous failure (a property of that one network call, not of
    // the artifact) still needs the generation check, to avoid a stale duplicate error replacing a
    // more recent one.
    const generation = ++resultFetchGenerationRef.current;
    const controller = controllerRef.current;
    const resultResult = await getResult(client, resultArtifactId, { signal: controller?.signal });
    if (
      controller?.signal.aborted ||
      // `controllerRef`'s controller lives for the whole component, not per logical run, so it
      // never aborts a call like this one on its own just because a *newer* session has since
      // started -- a call belonging to any session other than the currently active one is stale
      // by definition, whatever it resolved with (including a "deterministic" outcome below: that
      // determinism only holds within one session's own artifact, not across a completely
      // different, superseding one).
      scenarioSessionId !== activeScenarioSessionIdRef.current ||
      resultFetchSettledRef.current
    ) {
      return;
    }
    if (!resultResult.ok) {
      if (isResultNotFound(resultResult.error) || isResultUnavailable(resultResult.error)) {
        // Permanently unavailable, not transient: the backend has definitively rejected this
        // artifact id (e.g. it failed canonical/schema validation) or doesn't recognize it at
        // all. Repeating the same GET can never succeed, so this must not land on
        // "result-fetch-error" -- that state hides the form and offers only a same-artifact
        // retry, which would strand the user in a permanent dead end while still claiming "Your
        // result is ready". This session's own start is as dead as its result: only a fresh run
        // (a new Idempotency-Key) has any chance of a usable result.
        resultFetchSettledRef.current = true;
        enterUnknownError();
        return;
      }
      // Transient/ambiguous: the scenario itself already completed, only this GET failed (network
      // blip, transient 5xx). Landing on "unknown-error" here would let its retry clear
      // pendingStart and mint a fresh Idempotency-Key, starting a whole new (quota-consuming) run
      // for a result that already exists -- so this gets its own retry path instead. Only shown if
      // no newer retry has since started, so a stale failure can't replace a more recent outcome.
      if (generation !== resultFetchGenerationRef.current) {
        return;
      }
      setPhase({ kind: "result-fetch-error", scenarioSessionId, resultArtifactId, checkpointId });
      return;
    }
    const extracted = definition.extractResult(resultResult.value.output);
    if (extracted === null) {
      // The backend returned a genuinely unusable/malformed result -- an unexpected terminal
      // state, not a fetch problem, so this one *does* mean starting over.
      resultFetchSettledRef.current = true;
      enterUnknownError();
      return;
    }
    resultFetchSettledRef.current = true;
    setPhase({ kind: "result", scenarioSessionId, checkpointId, result: extracted });
    emitEvent(onEventRef.current, { type: "scenario_completed", scenarioSessionId, guestId });
  }

  // Shared by handleSubmit/handleRetry: both begin a (new or reused) prepared start the same way.
  function beginStart(prepared: PreparedScenarioStart) {
    setPhase({ kind: "submitting" });
    emitEvent(onEventRef.current, { type: "form_submitted", guestId });
    void runStart(prepared);
  }

  // Shared by handleSubmit and handleRetry (the "Try again" button on retryable-error): always
  // validates and reuses-or-rebuilds against the *current* values, never blindly replays whatever
  // was captured at the original submit. A field edited after a retryable failure (the form stays
  // editable in that phase) must actually reach the backend, not be silently discarded by a retry
  // that reused the stale prepared request; only truly unchanged values reuse the same
  // PreparedScenarioStart/Idempotency-Key (see prepareScenarioStart()'s own ANY-150 contract).
  function submitCurrentValues() {
    // guestId undefined here means either the initial identity fetch never succeeded, or (after a
    // guest_identity_not_found self-heal) the refresh itself failed -- prepareScenarioStart() would
    // still build a request, just with a null guest_id, which the backend has no way to accept.
    // Matches the ordinary Submit button's own `identityUnavailable` guard below, so "Try again"
    // can't bypass it and mint a doomed prepared start/Idempotency-Key that only loops the user on
    // the same failure.
    if (boot.kind !== "ready" || phase.kind === "submitting" || phase.kind === "running" || guestId === undefined) {
      return;
    }
    const errors = definition.validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      requestAnimationFrame(() => {
        formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      });
      return;
    }
    const reuseExisting = pendingStart !== null && shallowEqualValues(pendingStart.input, values);
    const prepared = reuseExisting
      ? pendingStart.prepared
      : prepareScenarioStart({
          productId,
          scenarioId: boot.scenarioId,
          frontendId: boot.frontendId,
          input: definition.toInput(values),
          guestId,
        });
    if (!reuseExisting) {
      setPendingStart({ prepared, input: values });
    }
    beginStart(prepared);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submitCurrentValues();
  }

  function handleRetry() {
    if (phase.kind !== "retryable-error") {
      return;
    }
    submitCurrentValues();
  }

  function handleRetryResult() {
    if (phase.kind !== "result-fetch-error") {
      return;
    }
    void fetchResult(phase.scenarioSessionId, phase.resultArtifactId, phase.checkpointId);
  }

  // The clipboard write always happens; the `copy_result` activation is only recorded when the
  // session has an active checkpoint to record it against (`currentCheckpointId` is legitimately
  // nullable on a completed session -- there is nothing to validate the next action against).
  // Either way, a failed activation-record must never make an already-copied, already-displayed
  // result look broken (ANY-243): `copied` reflects only the clipboard write, never the
  // activation's own HTTP outcome (see `copyResultAndRecordActivation`'s own contract).
  // Resolves as soon as the clipboard write itself succeeds (via `onCopied`), not once the
  // `copy_result` activation record also completes -- code review finding: awaiting the whole
  // helper before resolving made "Copied" wait on a network round-trip it never used to wait on.
  // The activation record still proceeds to completion in the background either way.
  //
  // Deliberately NOT tied to this mount's AbortSignal (code review finding): once the clipboard
  // write succeeds, the copy has irreversibly happened, so recording it must survive the page
  // going away (a mode switch remount, navigating off) instead of being cancelled -- before it's
  // even sent if the write was still pending, or mid-flight otherwise -- which would silently drop
  // the journey's required `copy_result`. It can't hang past unmount: the client applies its own
  // request timeout, and nothing here touches component state after unmount (`resolve` only
  // settles a promise; a setState on an unmounted ResultView is a no-op).
  function handleCopy(text: string): Promise<boolean> {
    if (phase.kind !== "result") {
      return Promise.resolve(false);
    }
    const { scenarioSessionId, checkpointId } = phase;
    const writeToClipboard = (value: string) =>
      navigator.clipboard?.writeText
        ? navigator.clipboard.writeText(value)
        : Promise.reject(new Error("Clipboard API unavailable."));

    return new Promise<boolean>((resolve) => {
      void copyResultAndRecordActivation(
        client,
        {
          text,
          scenarioSessionId,
          checkpointId,
          writeToClipboard,
          onCopied: () => {
            emitEvent(onEventRef.current, { type: "copy_activated", scenarioSessionId, guestId });
            resolve(true);
          },
        },
      ).then(
        (outcome) => {
          if (!outcome.copied) {
            resolve(false);
          }
        },
        // Code review finding: with no rejection handler here, a throwing `onCopied` (or anything
        // else in that chain) would leave this promise -- and the Copy button -- hanging forever
        // with no feedback. `resolve(false)` is a no-op if `onCopied` already resolved `true`.
        () => resolve(false),
      );
    });
  }

  function handleStartAnother() {
    if (phase.kind !== "result" || guestId === undefined) {
      return;
    }
    setValues(definition.emptyValues);
    setFieldErrors({});
    setPendingStart(null);
    activeScenarioSessionIdRef.current = null;
    setPhase({ kind: "idle" });

    getQuota(client, { productId, guestId, scenarioId }).then((quotaResult) => {
      if (controllerRef.current?.signal.aborted || !quotaResult.ok) {
        return;
      }
      setQuota(quotaResult.value);
      if (quotaResult.value.exhausted) {
        setPhase((prev) => (prev.kind === "idle" ? { kind: "quota-exhausted" } : prev));
      }
    }, _noop);
  }

  function updateField<K extends keyof V>(field: K, value: V[K]) {
    // Gated on a resolved guestId too, the same way submitCurrentValues() already gates
    // form_submitted: a boot-time createGuestIdentity() failure (not just the guest-identity-
    // not-found self-heal path) otherwise leaves the form fully interactive with guestId
    // undefined, and this event only ever fires once per (client, eventScopeKey) -- firing it here
    // with no guestId/scenarioSessionId would be permanently dropped by the backend's
    // identity-required check with no chance to recover it later. Leaving it unmarked-fired while
    // guestId is undefined lets a still-unresolved identity emit on a later keystroke instead of
    // losing the event outright.
    if (!hasEventFired(client, eventScopeKey, "form_started") && guestId !== undefined) {
      markEventFired(client, eventScopeKey, "form_started");
      emitEvent(onEventRef.current, { type: "form_started", guestId });
    }
    setValues((prev) => {
      const next = { ...prev };
      next[field] = value;
      return next;
    });
  }

  if (boot.kind === "loading") {
    return (
      <main className="page-container">
        <p role="status">{th("loading", { product: title })}</p>
      </main>
    );
  }
  if (boot.kind === "boot-error") {
    return (
      <main className="page-container">
        <ErrorState message={th("unavailable", { product: title })} />
      </main>
    );
  }

  const identityUnavailable = guestId === undefined;

  // Exhaustive over Phase["kind"] (docs/agent/coding-conventions.md's "Exhaustiveness" rule): a
  // future new Phase variant fails typecheck here instead of silently falling through to the form.
  let mainContent: ReactNode;
  switch (phase.kind) {
    case "result":
      mainContent = (
        <div className={styles.resultStack}>
          <Result result={phase.result} onCopy={handleCopy} />
          {definition.hasStartAnother ? (
            <Button className={styles.resultAction} variant="secondary" onClick={handleStartAnother}>
              {tp(`${definition.messageScope}.startAnother`)}
            </Button>
          ) : null}
        </div>
      );
      break;
    case "quota-exhausted":
      mainContent = <ErrorState message={th("quotaExhausted", { product: title })} />;
      break;
    case "result-fetch-error":
      // No form here: the scenario run already succeeded and consumed its quota unit -- showing
      // the form again would invite a second, wasteful run instead of just re-fetching the result
      // that already exists.
      mainContent = (
        <ErrorState message={th("resultFetchFailed")} onRetry={handleRetryResult} />
      );
      break;
    case "idle":
    case "submitting":
    case "running":
    case "retryable-error":
    case "unknown-error":
      mainContent = (
        <Card className={styles.formCard}>
          <form
            ref={formRef}
            aria-label={`${title} form`}
            className={styles.form}
            noValidate
            onSubmit={handleSubmit}
          >
            <Fields values={values} errors={fieldErrors} disabled={busy || identityUnavailable} onChange={updateField} />
            <div className={styles.footer}>
              <Button type="submit" loading={busy} disabled={identityUnavailable}>
                {phase.kind === "submitting"
                  ? th("starting")
                  : phase.kind === "running"
                    ? th("generating")
                    : tp(`${definition.messageScope}.submit`)}
              </Button>
              <div className={styles.statusRegion}>
                {phase.kind === "running" ? <p role="status">{tp(`${definition.messageScope}.running`)}</p> : null}
                {identityUnavailable ? <p role="alert">{th("identityUnavailable")}</p> : null}
              </div>
            </div>
          </form>
        </Card>
      );
      break;
    default:
      return assertNever(phase);
  }

  return (
    <main className="page-container">
      <div className={styles.content}>
        <header className={styles.header}>
          <h1>{title}</h1>
          {definition.hasDescription ? <p className={styles.description}>{tp("description")}</p> : null}
          {quota ? (
            <p className={styles.quota} aria-live="polite">
              {tp("quotaRemaining", { remaining: quota.remainingCount, limit: quota.limitCount })}
            </p>
          ) : null}
        </header>

        {mainContent}

      {phase.kind === "retryable-error" ? (
        // Not gated on `pendingStart`: submitCurrentValues() (called by both this and the form's
        // own Submit button) builds a fresh prepared start when there's none to reuse -- e.g.
        // after the guest-identity self-heal path in runStart(), which clears pendingStart while
        // still landing on retryable-error. It IS gated on `identityUnavailable`: when the
        // self-heal's own refresh failed too, there's no valid guest id to submit with, and the
        // form's own "We couldn't verify your identity. Please reload the page and try again."
        // message (rendered above, inside the form) is the only path back -- offering a "Try
        // again" here would only loop the user on a doomed retry.
        <ErrorState
          message={th(`errors.${phase.reason}`, { product: title })}
          onRetry={identityUnavailable ? undefined : handleRetry}
        />
      ) : null}
      {phase.kind === "unknown-error" ? (
        <ErrorState
          message={tp(`${definition.messageScope}.runFailed`)}
          onRetry={() => {
            // pendingStart was already cleared the moment this phase was entered (see
            // enterUnknownError()) -- this button (like the form's own Submit button, which stays
            // reachable while this phase is showing) is guaranteed a fresh Idempotency-Key either
            // way; it only needs to get the phase back to a submittable state.
            setPhase({ kind: "idle" });
          }}
        />
      ) : null}
      </div>
    </main>
  );
}

function _noop(): void {
  // Deliberately discards a settled promise's value/rejection -- see call sites' comments.
}
