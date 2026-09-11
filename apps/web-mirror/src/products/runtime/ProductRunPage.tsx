"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  createInMemoryAsyncStorage,
  createWindowLocalStorageAdapter,
  getQuota,
  getResult,
  getRuntimeConfig,
  isGuestIdentityNotFound,
  isQuotaExhausted,
  isResultNotFound,
  isResultUnavailable,
  nextAction,
  pollScenarioSession,
  prepareScenarioStart,
  refreshGuestIdentity,
  type AsyncStorage,
  type PlatformApiClient,
  type PreparedScenarioStart,
  type QuotaState,
} from "@anytoolai/ce-kit";
import { ErrorState } from "../../components/ErrorState";
import type { ProductDefinition, ProductRunEvent } from "./productDefinition";

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

function shallowEqualValues<V extends Record<string, unknown>>(a: V, b: V): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => Object.is(a[key], b[key]));
}

type BootState =
  | { kind: "loading" }
  | { kind: "boot-error" }
  | { kind: "ready"; scenarioId: string; frontendId: string };

type Phase<R> =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; scenarioSessionId: string }
  | { kind: "result"; scenarioSessionId: string; checkpointId: string | null; result: R }
  | { kind: "quota-exhausted" }
  | { kind: "retryable-error"; message: string }
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
}: ProductRunPageProps<V, R>) {
  const { Fields, Result } = definition;

  // Always-current `onEvent` behind a ref, refreshed after every render. Used by every
  // emitEvent() call site below, not just the mount effect: `handleSubmit`/`handleRetry`/
  // `updateField` are genuinely synchronous DOM-event-handler closures where using the `onEvent`
  // prop directly would already be safe, but `runPoll` (a multi-second async continuation) and
  // `handleCopied` (invoked from the product renderer's own clipboard-write promise, itself
  // async) are not -- either can run after a re-render has already handed the parent a new
  // `onEvent` identity, and a closure captured before that await would fire the stale one. Using
  // the ref uniformly, rather than trying to classify each call site as "safe," avoids
  // re-introducing this exact bug: an earlier version used `onEvent` directly in `runPoll`.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });
  // Guards against React StrictMode's dev-only double-invoke of effects (mount -> cleanup ->
  // remount) double-counting this top-of-funnel event; the ref survives that synthetic cycle
  // since it's the same component instance throughout.
  const productViewedFiredRef = useRef(false);
  useEffect(() => {
    if (productViewedFiredRef.current) {
      return;
    }
    productViewedFiredRef.current = true;
    emitEvent(onEventRef.current, { type: "product_viewed" });
  }, []);
  const formStartedRef = useRef(false);
  // Bumped by every fetchResult() call; see that function's own comment for why.
  const resultFetchGenerationRef = useRef(0);
  // True once any concurrent fetchResult() call for the current session has reached a definitive,
  // artifact-deterministic outcome (a usable result, a malformed one, or a permanently-unavailable
  // rejection); reset per session at the top of runPoll(). See fetchResult()'s own comment.
  const resultFetchSettledRef = useRef(false);

  const [boot, setBoot] = useState<BootState>({ kind: "loading" });
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const [guestId, setGuestId] = useState<string | undefined>(undefined);
  const [ephemeralGuestStorage] = useState<AsyncStorage>(() => createInMemoryAsyncStorage());
  const [guestStorage] = useState<AsyncStorage>(() => createWindowLocalStorageAdapter() ?? ephemeralGuestStorage);
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
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const [values, setValues] = useState<V>(definition.emptyValues);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof V, string>>>({});
  const [phase, setPhase] = useState<Phase<R>>({ kind: "idle" });
  // Holds the one Idempotency-Key-bound handle for the current logical submission (ANY-150): a
  // "Try again" after a retryable failure reuses `.execute()` on this same handle so the backend
  // can collapse a duplicate submit into the original session instead of spending quota twice.
  // Editing any field after a failure makes the next submit build a genuinely new handle instead.
  const [pendingStart, setPendingStart] = useState<{ prepared: PreparedScenarioStart; input: V } | null>(null);

  const productId = definition.productId;
  const scenarioId = definition.scenarioId;
  useEffect(() => {
    // Snapshotted once per effect invocation (including StrictMode's replay), not re-read from
    // controllerRef inside the .then() continuations below: by the time those run, the ref could
    // already point at a newer controller from a later invocation, which would wrongly report
    // "not aborted" for a continuation that belongs to an already-superseded one.
    const controller = controllerRef.current;
    Promise.all([getRuntimeConfig(client, productId), client.createGuestIdentity({ storage: guestStorage })]).then(
      ([runtimeResult, guestResult]) => {
        if (controller?.signal.aborted) {
          return;
        }
        const resolvedGuestId = guestResult.ok ? guestResult.value.guestId : undefined;
        setGuestId(resolvedGuestId);
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
        }
      },
    );
  }, [client, guestStorage, productId, scenarioId]);

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
        const fresh = await refreshGuestIdentity(client, guestStorage, { fallbackStorage: ephemeralGuestStorage });
        if (controller?.signal.aborted) {
          return;
        }
        setGuestId(fresh.ok ? fresh.value.guestId : undefined);
        setPendingStart(null);
        setPhase({ kind: "retryable-error", message: "Please try again." });
        return;
      }
      setPhase({ kind: "retryable-error", message: `Could not start ${definition.title}. Please try again.` });
      return;
    }
    setPhase({ kind: "running", scenarioSessionId: result.value.scenarioSessionId });
    void runPoll(result.value.scenarioSessionId);
  }

  async function runPoll(scenarioSessionId: string) {
    // Fresh per logical run: this session's result-fetch lifecycle (this call plus any later
    // handleRetryResult() retries against the same artifact) hasn't settled yet.
    resultFetchSettledRef.current = false;
    const controller = controllerRef.current;
    const polled = await pollScenarioSession(client, scenarioSessionId, { signal: controller?.signal });
    if (controller?.signal.aborted) {
      return;
    }
    if (!polled.result.ok) {
      setPhase({
        kind: "retryable-error",
        message:
          polled.reason === "timeout"
            ? "This is taking longer than expected. Please try again."
            : "Lost connection while waiting for your result. Please try again.",
      });
      return;
    }
    if (polled.reason === "timeout") {
      // pollScenarioSession() returning `result.ok: true` together with `reason: "timeout"` means
      // the *last* snapshot it saw was still non-terminal (started/running) when the bounded
      // polling budget ran out -- not a backend conclusion about the run, just this poll giving
      // up early. Treating that as enterUnknownError() (like a genuinely terminal status below)
      // would clear pendingStart and abandon a job that may still be actively running server-side.
      // Ambiguous, so this is retryable-error: its retry reuses the same Idempotency-Key, and the
      // backend collapses that back onto this same session rather than starting a new one.
      setPhase({ kind: "retryable-error", message: "This is taking longer than expected. Please try again." });
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
    if (controller?.signal.aborted || resultFetchSettledRef.current) {
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
    emitEvent(onEventRef.current, { type: "scenario_completed", scenarioSessionId });
  }

  // Shared by handleSubmit/handleRetry: both begin a (new or reused) prepared start the same way.
  function beginStart(prepared: PreparedScenarioStart) {
    setPhase({ kind: "submitting" });
    emitEvent(onEventRef.current, { type: "form_submitted" });
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

  function handleCopied() {
    if (phase.kind !== "result") {
      return;
    }
    // Emitted on a successful clipboard write regardless of the next-action HTTP outcome below,
    // and regardless of whether this session even has a checkpoint id (`currentCheckpointId` is
    // legitimately nullable on a completed session) -- the funnel event reflects the user's copy,
    // not the backend's acknowledgement of it.
    emitEvent(onEventRef.current, { type: "copy_activated", scenarioSessionId: phase.scenarioSessionId });
    if (!phase.checkpointId) {
      return;
    }
    // Fire-and-forget: a failed activation event must never make an already-copied,
    // already-displayed result look broken (ANY-243).
    nextAction(
      client,
      {
        scenarioSessionId: phase.scenarioSessionId,
        nextActionId: definition.copyNextActionId,
        checkpointId: phase.checkpointId,
      },
      { signal: controllerRef.current?.signal },
    ).then(_noop, _noop);
  }

  function updateField<K extends keyof V>(field: K, value: V[K]) {
    if (!formStartedRef.current) {
      formStartedRef.current = true;
      emitEvent(onEventRef.current, { type: "form_started" });
    }
    setValues((prev) => {
      const next = { ...prev };
      next[field] = value;
      return next;
    });
  }

  if (boot.kind === "loading") {
    return <p role="status">Loading {definition.title}…</p>;
  }
  if (boot.kind === "boot-error") {
    return <ErrorState message={`${definition.title} is unavailable right now. Please reload the page.`} />;
  }

  const busy = phase.kind === "submitting" || phase.kind === "running";
  const identityUnavailable = guestId === undefined;

  // Exhaustive over Phase["kind"] (docs/agent/coding-conventions.md's "Exhaustiveness" rule): a
  // future new Phase variant fails typecheck here instead of silently falling through to the form.
  let mainContent: ReactNode;
  switch (phase.kind) {
    case "result":
      mainContent = <Result result={phase.result} onCopied={handleCopied} />;
      break;
    case "quota-exhausted":
      mainContent = <ErrorState message={`You've used all your ${definition.title} runs for now.`} />;
      break;
    case "result-fetch-error":
      // No form here: the scenario run already succeeded and consumed its quota unit -- showing
      // the form again would invite a second, wasteful run instead of just re-fetching the result
      // that already exists.
      mainContent = (
        <ErrorState message="Your result is ready, but we couldn't load it. Please try again." onRetry={handleRetryResult} />
      );
      break;
    case "idle":
    case "submitting":
    case "running":
    case "retryable-error":
    case "unknown-error":
      mainContent = (
        <form onSubmit={handleSubmit}>
          <Fields values={values} errors={fieldErrors} disabled={busy} onChange={updateField} />
          <button type="submit" disabled={busy || identityUnavailable}>
            {phase.kind === "submitting" ? "Starting…" : phase.kind === "running" ? "Generating…" : definition.copy.submit}
          </button>
          {phase.kind === "running" ? <p role="status">{definition.copy.running}</p> : null}
          {identityUnavailable ? (
            <p role="alert">We couldn&apos;t verify your identity. Please reload the page and try again.</p>
          ) : null}
        </form>
      );
      break;
    default:
      return assertNever(phase);
  }

  return (
    <main>
      <h1>{definition.title}</h1>
      {quota ? <p aria-live="polite">{definition.copy.quotaRemaining(quota.remainingCount, quota.limitCount)}</p> : null}

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
        <ErrorState message={phase.message} onRetry={identityUnavailable ? undefined : handleRetry} />
      ) : null}
      {phase.kind === "unknown-error" ? (
        <ErrorState
          message={definition.copy.runFailed}
          onRetry={() => {
            // pendingStart was already cleared the moment this phase was entered (see
            // enterUnknownError()) -- this button (like the form's own Submit button, which stays
            // reachable while this phase is showing) is guaranteed a fresh Idempotency-Key either
            // way; it only needs to get the phase back to a submittable state.
            setPhase({ kind: "idle" });
          }}
        />
      ) : null}
    </main>
  );
}

function assertNever(value: never): never {
  throw new Error(`Unhandled Phase: ${JSON.stringify(value)}`);
}

function _noop(): void {
  // Deliberately discards a settled promise's value/rejection -- see call sites' comments.
}
