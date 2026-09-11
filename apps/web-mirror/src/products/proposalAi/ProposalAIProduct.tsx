"use client";

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import {
  createInMemoryAsyncStorage,
  createWindowLocalStorageAdapter,
  getQuota,
  getResult,
  getRuntimeConfig,
  isGuestIdentityNotFound,
  isQuotaExhausted,
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
import { ResultView } from "../../components/ResultView";

/**
 * Funnel events ANY-243 names (product viewed -> form started -> form submitted -> scenario
 * completed/result viewed -> copy activation). Never carries prompt text, result text, or
 * clipboard contents -- only ids/status, matching ANY-453's "keep ... user text out of event
 * payloads" requirement.
 */
export type ProposalAIProductEvent =
  | { type: "product_viewed" }
  | { type: "form_started" }
  | { type: "form_submitted" }
  | { type: "scenario_completed"; scenarioSessionId: string }
  | { type: "copy_activated"; scenarioSessionId: string };

export type ProposalAIProductProps = {
  client: PlatformApiClient;
  /**
   * Generic event integration point (ANY-453's "The foundation exposes callbacks/integration
   * points and tests them with injected handlers; product integration verifies the real event
   * path after both prerequisites are ready" -- ANY-17 owns that real event path). No real
   * dispatch is wired here; this only exposes and tests the callback contract.
   */
  onEvent?: (event: ProposalAIProductEvent) => void;
};

/**
 * Invokes a caller-supplied event handler defensively: neither a synchronous throw nor an async
 * handler's later rejection (TS's `() => void` return type structurally accepts `() => Promise<void>`,
 * so an `async` handler is a legal `onEvent`) may break the product page (ANY-453: "keep analytics
 * failure non-blocking"). `Promise.resolve(...)` correctly adopts a genuine thenable and just
 * wraps a plain sync return value otherwise, so no manual `.then`-sniffing is needed.
 */
function emitEvent(
  handler: ((event: ProposalAIProductEvent) => void) | undefined,
  event: ProposalAIProductEvent,
): void {
  try {
    Promise.resolve(handler?.(event)).catch(_noop);
  } catch {
    // handler threw synchronously -- nothing to attach a rejection handler to.
  }
}

const PRODUCT_ID = "proposal_ai";
const COPY_NEXT_ACTION_ID = "copy_result";
const TONE_OPTIONS = ["neutral", "warm", "firm"] as const;
type Tone = (typeof TONE_OPTIONS)[number];

type FormValues = {
  taskText: string;
  freelancerPositioning: string;
  tone: Tone | "";
  language: string;
};

const EMPTY_VALUES: FormValues = { taskText: "", freelancerPositioning: "", tone: "", language: "" };

type FieldErrors = Partial<Record<keyof FormValues, string>>;

// Mirrors generate_input.schema.json's `language` pattern; task_text/freelancer_positioning are
// checked structurally below instead of transcribing that schema's equivalent (but harder to
// read) regex. Backend validation stays authoritative either way.
const LANGUAGE_PATTERN = /^[a-z]{2}(-[A-Z]{2})?$/;

function validate(values: FormValues): FieldErrors {
  const errors: FieldErrors = {};
  for (const [field, label] of [
    ["taskText", "Task description"],
    ["freelancerPositioning", "Your positioning"],
  ] as const) {
    const value = values[field];
    if (value.trim().length === 0) {
      errors[field] = `${label} is required.`;
    } else if (value !== value.trim()) {
      errors[field] = `${label} must not start or end with whitespace.`;
    } else if (value.length > 4000) {
      errors[field] = `${label} must be 4000 characters or fewer.`;
    }
  }
  if (values.language && !LANGUAGE_PATTERN.test(values.language)) {
    errors.language = 'Language must look like "en" or "en-US".';
  }
  return errors;
}

function toApiInput(values: FormValues): Record<string, unknown> {
  return {
    task_text: values.taskText,
    freelancer_positioning: values.freelancerPositioning,
    ...(values.tone ? { tone: values.tone } : {}),
    ...(values.language ? { language: values.language } : {}),
  };
}

function shallowEqualValues(a: FormValues, b: FormValues): boolean {
  return (
    a.taskText === b.taskText &&
    a.freelancerPositioning === b.freelancerPositioning &&
    a.tone === b.tone &&
    a.language === b.language
  );
}

/**
 * renderer_contract.yaml pins `text` as the sole rendered field for
 * `kernel.schemas.compose_persuasive_text_output_v1` -- angle/rationale/model/provider are
 * excluded on purpose and must never reach this component.
 */
function extractProposalText(output: Record<string, unknown>): string | null {
  const text = output.text;
  return typeof text === "string" ? text : null;
}

type BootState =
  | { kind: "loading" }
  | { kind: "boot-error" }
  | { kind: "ready"; scenarioId: string; frontendId: string };

type Phase =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; scenarioSessionId: string }
  | { kind: "result"; scenarioSessionId: string; checkpointId: string | null; text: string }
  | { kind: "quota-exhausted" }
  | { kind: "retryable-error"; message: string }
  | { kind: "unknown-error" };

/**
 * ProposalAI's product page: guest identity + runtime config + advisory quota on mount, a form
 * for task_text/freelancer_positioning/tone/language, an idempotent scenario start, bounded
 * polling, and the canonical text result with copy-to-clipboard activation.
 *
 * This is deliberately a concrete, product-owned component rather than a generic
 * `ProductRunPage(definition)` -- per ANY-453's team-lead guidance (docs/exec-plans/active/
 * any-453-shared-web-product-runtime-foundation.md): build the first real product, extract a
 * shared abstraction only once a second product needs the same shape. Nothing here should be
 * assumed reusable yet.
 */
export function ProposalAIProduct({ client, onEvent }: ProposalAIProductProps) {
  // Always-current `onEvent` behind a ref, refreshed after every render. Used by every
  // emitEvent() call site below, not just the mount effect: `handleSubmit`/`handleRetry`/
  // `updateField` are genuinely synchronous DOM-event-handler closures where using the `onEvent`
  // prop directly would already be safe, but `runPoll` (a multi-second async continuation) and
  // `handleCopied` (invoked from `ResultView`'s own clipboard-write promise, itself async) are
  // not -- either can run after a re-render has already handed the parent a new `onEvent`
  // identity, and a closure captured before that await would fire the stale one. Using the ref
  // uniformly, rather than trying to classify each call site as "safe," avoids re-introducing
  // this exact bug: an earlier version used `onEvent` directly in `runPoll`, which was wrong.
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

  const [boot, setBoot] = useState<BootState>({ kind: "loading" });
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const [guestId, setGuestId] = useState<string | undefined>(undefined);
  const [ephemeralGuestStorage] = useState<AsyncStorage>(() => createInMemoryAsyncStorage());
  const [guestStorage] = useState<AsyncStorage>(() => createWindowLocalStorageAdapter() ?? ephemeralGuestStorage);
  // Fresh AbortController created inside the effect itself, not a `useState` singleton: aborts
  // every in-flight read (identity/runtime-config/quota on mount, poll/result while a run is
  // active) on unmount so none of them can call setState after this component is gone. A
  // `useState`-held controller would be the SAME instance across React StrictMode's double-invoke
  // of effects (mount -> cleanup -> remount) -- confirmed live: neither this app's default `next
  // dev` config nor an explicit `reactStrictMode: true` actually reproduces that double-invoke
  // for this route today (no duplicate network calls observed either way), so this isn't a
  // currently-reproducing bug in this app -- but a `useState` controller is still objectively
  // fragile to it: that cleanup's abort() would permanently kill the single shared instance
  // before the remount's own effects (or any later user action) ever got to use it, leaving every
  // subsequent request short-circuited by `signal.aborted` forever (stuck on "Loading
  // ProposalAI..." with no submit ever able to succeed) the moment StrictMode *does* apply --
  // whether from this app opting in later or a future Next.js version defaulting it on.
  // Recreating the controller inside the effect gives each invocation, including a StrictMode
  // replay, its own independent, un-aborted controller, which is correct either way.
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const [values, setValues] = useState<FormValues>(EMPTY_VALUES);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  // Holds the one Idempotency-Key-bound handle for the current logical submission (ANY-150): a
  // "Try again" after a retryable failure reuses `.execute()` on this same handle so the backend
  // can collapse a duplicate submit into the original session instead of spending quota twice.
  // Editing any field after a failure makes the next submit build a genuinely new handle instead.
  const [pendingStart, setPendingStart] = useState<{ prepared: PreparedScenarioStart; input: FormValues } | null>(
    null,
  );

  useEffect(() => {
    // Snapshotted once per effect invocation (including StrictMode's replay), not re-read from
    // controllerRef inside the .then() continuations below: by the time those run, the ref could
    // already point at a newer controller from a later invocation, which would wrongly report
    // "not aborted" for a continuation that belongs to an already-superseded one.
    const controller = controllerRef.current;
    Promise.all([getRuntimeConfig(client, PRODUCT_ID), client.createGuestIdentity({ storage: guestStorage })]).then(
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
        const scenario = runtimeResult.value.scenarios[0];
        const frontend =
          runtimeResult.value.frontends.find((candidate) => candidate.type === "web" && candidate.enabled) ??
          runtimeResult.value.frontends[0];
        if (!scenario || !frontend) {
          setBoot({ kind: "boot-error" });
          return;
        }
        setBoot({ kind: "ready", scenarioId: scenario.scenarioId, frontendId: frontend.frontendId });

        if (resolvedGuestId) {
          // Advisory only: shown if it loads in time, never blocks the form from becoming usable.
          getQuota(client, { productId: PRODUCT_ID, guestId: resolvedGuestId }).then((quotaResult) => {
            if (controller?.signal.aborted || !quotaResult.ok) {
              return;
            }
            setQuota(quotaResult.value);
            if (quotaResult.value.exhausted) {
              setPhase({ kind: "quota-exhausted" });
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
  }, [client, guestStorage]);

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
      setPhase({ kind: "retryable-error", message: "Could not start ProposalAI. Please try again." });
      return;
    }
    setPhase({ kind: "running", scenarioSessionId: result.value.scenarioSessionId });
    void runPoll(result.value.scenarioSessionId);
  }

  async function runPoll(scenarioSessionId: string) {
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
            : "Lost connection while generating your proposal. Please try again.",
      });
      return;
    }
    const session = polled.result.value;
    if (session.status !== "completed") {
      // `failed`/`expired`/`waiting_for_user` (the latter never legitimately happens for this
      // single-step workflow) all land on the generic safe-error state rather than guessing at
      // product copy for a status this scenario isn't expected to reach.
      setPhase({ kind: "unknown-error" });
      return;
    }
    if (!session.resultArtifactId) {
      setPhase({ kind: "unknown-error" });
      return;
    }
    const resultResult = await getResult(client, session.resultArtifactId, { signal: controller?.signal });
    if (controller?.signal.aborted) {
      return;
    }
    const text = resultResult.ok ? extractProposalText(resultResult.value.output) : null;
    if (!text) {
      setPhase({ kind: "unknown-error" });
      return;
    }
    setPhase({ kind: "result", scenarioSessionId, checkpointId: session.currentCheckpointId, text });
    emitEvent(onEventRef.current, { type: "scenario_completed", scenarioSessionId });
  }

  // Shared by handleSubmit/handleRetry: both begin a (new or reused) prepared start the same way.
  function beginStart(prepared: PreparedScenarioStart) {
    setPhase({ kind: "submitting" });
    emitEvent(onEventRef.current, { type: "form_submitted" });
    void runStart(prepared);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (boot.kind !== "ready" || phase.kind === "submitting" || phase.kind === "running") {
      return;
    }
    const errors = validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }
    const reuseExisting = pendingStart !== null && shallowEqualValues(pendingStart.input, values);
    const prepared = reuseExisting
      ? pendingStart.prepared
      : prepareScenarioStart({
          productId: PRODUCT_ID,
          scenarioId: boot.scenarioId,
          frontendId: boot.frontendId,
          input: toApiInput(values),
          guestId,
        });
    if (!reuseExisting) {
      setPendingStart({ prepared, input: values });
    }
    beginStart(prepared);
  }

  function handleRetry() {
    if (phase.kind !== "retryable-error" || !pendingStart) {
      return;
    }
    beginStart(pendingStart.prepared);
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
      { scenarioSessionId: phase.scenarioSessionId, nextActionId: COPY_NEXT_ACTION_ID, checkpointId: phase.checkpointId },
      { signal: controllerRef.current?.signal },
    ).then(_noop, _noop);
  }

  function updateField<K extends keyof FormValues>(field: K, value: FormValues[K]) {
    if (!formStartedRef.current) {
      formStartedRef.current = true;
      emitEvent(onEventRef.current, { type: "form_started" });
    }
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  if (boot.kind === "loading") {
    return <p role="status">Loading ProposalAI…</p>;
  }
  if (boot.kind === "boot-error") {
    return <ErrorState message="ProposalAI is unavailable right now. Please reload the page." />;
  }

  const busy = phase.kind === "submitting" || phase.kind === "running";
  const identityUnavailable = guestId === undefined;

  return (
    <main>
      <h1>ProposalAI</h1>
      {quota ? (
        <p aria-live="polite">
          {quota.remainingCount} of {quota.limitCount} proposals remaining.
        </p>
      ) : null}

      {phase.kind === "result" ? (
        <ResultView text={phase.text} onCopied={handleCopied} />
      ) : phase.kind === "quota-exhausted" ? (
        <ErrorState message="You've used all your ProposalAI runs for now." />
      ) : (
        <form onSubmit={handleSubmit}>
          <label htmlFor="proposal-ai-task-text">Describe the task</label>
          <textarea
            id="proposal-ai-task-text"
            value={values.taskText}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => updateField("taskText", event.target.value)}
            disabled={busy}
            aria-invalid={Boolean(fieldErrors.taskText)}
          />
          {fieldErrors.taskText ? <p role="alert">{fieldErrors.taskText}</p> : null}

          <label htmlFor="proposal-ai-positioning">Your positioning</label>
          <textarea
            id="proposal-ai-positioning"
            value={values.freelancerPositioning}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
              updateField("freelancerPositioning", event.target.value)
            }
            disabled={busy}
            aria-invalid={Boolean(fieldErrors.freelancerPositioning)}
          />
          {fieldErrors.freelancerPositioning ? <p role="alert">{fieldErrors.freelancerPositioning}</p> : null}

          <label htmlFor="proposal-ai-tone">Tone (optional)</label>
          <select
            id="proposal-ai-tone"
            value={values.tone}
            onChange={(event: ChangeEvent<HTMLSelectElement>) => updateField("tone", event.target.value as Tone | "")}
            disabled={busy}
          >
            <option value="">Default</option>
            {TONE_OPTIONS.map((tone) => (
              <option key={tone} value={tone}>
                {tone}
              </option>
            ))}
          </select>

          <label htmlFor="proposal-ai-language">Language (optional)</label>
          <input
            id="proposal-ai-language"
            value={values.language}
            onChange={(event: ChangeEvent<HTMLInputElement>) => updateField("language", event.target.value)}
            disabled={busy}
            aria-invalid={Boolean(fieldErrors.language)}
          />
          {fieldErrors.language ? <p role="alert">{fieldErrors.language}</p> : null}

          <button type="submit" disabled={busy || identityUnavailable}>
            {phase.kind === "submitting" ? "Starting…" : phase.kind === "running" ? "Generating…" : "Generate proposal"}
          </button>
          {phase.kind === "running" ? <p role="status">Generating your proposal…</p> : null}
          {identityUnavailable ? (
            <p role="alert">We couldn&apos;t verify your identity. Please reload the page and try again.</p>
          ) : null}
        </form>
      )}

      {phase.kind === "retryable-error" ? (
        <ErrorState message={phase.message} onRetry={pendingStart ? handleRetry : undefined} />
      ) : null}
      {phase.kind === "unknown-error" ? (
        <ErrorState
          message="Something went wrong generating your proposal. Please try again."
          onRetry={() => setPhase({ kind: "idle" })}
        />
      ) : null}
    </main>
  );
}

function _noop(): void {
  // Deliberately discards a settled promise's value/rejection -- see call sites' comments.
}
