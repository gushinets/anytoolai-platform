import { useEffect, useRef, useState } from "react";
import {
  createChromeStorageAdapter,
  createChromeTabNavigator,
  createHandoff,
  isGuestIdentityNotFound,
  openHandoffConsent,
  pollScenarioSession,
  refreshGuestIdentity,
  startScenario,
  PlatformApiClient,
} from "@anytoolai/ce-kit";
import { CAPTURE_INPUT_MESSAGE, type CaptureInputResponse } from "../content/messages";
import { productConfig } from "../product.config";
import { runtimeConfig } from "../runtimeConfig";

type ViewState =
  | { kind: "idle" }
  | { kind: "running"; step: string }
  | { kind: "opened" }
  | { kind: "error"; message: string };

async function captureActiveTabInput(): Promise<CaptureInputResponse> {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTab?.id === undefined) {
    throw new Error("No active tab to capture input from.");
  }
  const response = (await chrome.tabs.sendMessage(activeTab.id, CAPTURE_INPUT_MESSAGE)) as
    | CaptureInputResponse
    | undefined;
  if (!response) {
    throw new Error("Could not capture input from the active tab.");
  }
  return response;
}

/**
 * Minimal source-side wiring for the ANY-224 handoff smoke journey: capture -> run
 * `kernel_demo.handoff_smoke_source_v1` to completion -> create a handoff -> open the backend-
 * owned consent page in a new tab. This is the only journey this ticket wires up (see
 * plans/ANY-224.md assumption 1) -- it deliberately does not build the general
 * Input/Progress/Result product experience.
 */
export function HandoffView() {
  const [state, setState] = useState<ViewState>({ kind: "idle" });
  const abortControllerRef = useRef<AbortController | null>(null);

  // If the sidepanel is closed/navigated away from mid-journey, abort the in-flight poll loop --
  // without this, pollScenarioSession() (up to ~30 GETs over its default 60s window) keeps hitting
  // the backend for a result nothing is listening for anymore.
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  async function runSmokeJourney() {
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setState({ kind: "running", step: "Capturing input…" });
    try {
      const client = new PlatformApiClient({ baseUrl: runtimeConfig.platformApiBaseUrl });
      // Named `guestStorage`, not `storage` -- see createLocalStorageAdapter()'s docstring for why
      // a bare `storage` identifier can't be used in a file bundled directly into this WXT build.
      const guestStorage = createChromeStorageAdapter(chrome.storage.local);

      // Capturing input from the active tab doesn't depend on guest-identity resolution -- run
      // them concurrently instead of paying the sum of both latencies.
      const [captured, guestIdentity] = await Promise.all([
        captureActiveTabInput(),
        client.createGuestIdentity({ storage: guestStorage }),
      ]);
      let guestId = guestIdentity.ok ? guestIdentity.value.guestId : undefined;

      const startSourceScenario = (id: string | undefined) =>
        startScenario(client, {
          productId: productConfig.productId,
          scenarioId: productConfig.handoffSourceScenarioId,
          frontendId: productConfig.frontendId,
          input: { source_text: captured.text },
          guestId: id,
        });

      setState({ kind: "running", step: "Running source scenario…" });
      let started = await startSourceScenario(guestId);
      if (!started.ok && isGuestIdentityNotFound(started.error)) {
        // The persisted guest id is stale (backend deleted it) -- self-heal the same way
        // HandoffConsent.tsx does for a stale id on accept(), then retry once with a fresh id.
        const refreshed = await refreshGuestIdentity(client, guestStorage);
        guestId = refreshed.ok ? refreshed.value.guestId : undefined;
        started = await startSourceScenario(guestId);
      }
      if (!started.ok) {
        throw new Error("Could not start the source scenario.");
      }

      setState({ kind: "running", step: "Waiting for the result…" });
      const polled = await pollScenarioSession(client, started.value.scenarioSessionId, {
        signal: controller.signal,
      });
      if (!polled.result.ok || polled.result.value.status !== "completed") {
        throw new Error("The source scenario did not complete.");
      }
      const resultArtifactId = polled.result.value.resultArtifactId;
      if (!resultArtifactId) {
        throw new Error("The source scenario completed without a result artifact.");
      }

      // The poll loop above already stops on unmount (its own signal), but createHandoff() and
      // openHandoffConsent() below have not started yet -- without this check, closing the
      // sidepanel right after a successful poll would still mint a real handoff and pop open a new
      // tab for a journey nobody is watching anymore.
      if (controller.signal.aborted) {
        return;
      }

      setState({ kind: "running", step: "Creating handoff…" });
      const handoff = await createHandoff(
        client,
        {
          handoffDefinitionId: productConfig.handoffDefinitionId,
          sourceScenarioSessionId: started.value.scenarioSessionId,
          sourceArtifactId: resultArtifactId,
        },
        { signal: controller.signal },
      );
      if (!handoff.ok) {
        throw new Error("Could not create the handoff.");
      }

      // openHandoffConsent() has no signal/cancellation of its own (it's a synchronous tab-open,
      // not a network call) -- this check is the only thing standing between an unmount and
      // opening a new tab the user never asked for anymore.
      if (controller.signal.aborted) {
        return;
      }

      await openHandoffConsent({
        webConsentBaseUrl: runtimeConfig.webConsentBaseUrl,
        handoffToken: handoff.value.handoffToken,
        navigate: createChromeTabNavigator(chrome.tabs),
      });
      setState({ kind: "opened" });
    } catch (error) {
      setState({ kind: "error", message: error instanceof Error ? error.message : "Something went wrong." });
    }
  }

  return (
    <div>
      <button type="button" onClick={runSmokeJourney} disabled={state.kind === "running"}>
        Run handoff smoke journey
      </button>
      {state.kind === "running" ? <p role="status">{state.step}</p> : null}
      {state.kind === "opened" ? <p role="status">Handoff created. Consent opened in a new tab.</p> : null}
      {state.kind === "error" ? <p role="alert">{state.message}</p> : null}
    </div>
  );
}
