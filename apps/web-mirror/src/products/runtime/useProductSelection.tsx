import { useEffect, useRef, useState } from "react";
import { clearPaidStartRecovery, getScenarioSession, readPaidStartRecovery,
  type PlatformApiClient, type ScenarioSession } from "@anytoolai/ce-kit";
import { Button, Card } from "@anytoolai/shared-ui";
import { ErrorState } from "../../components/ErrorState";
import { useHostT, useProductT } from "../../i18n";
import { getPaidPersistence } from "../../lib/portalSession";
import { forgetAttachSession, forgetChosenAttachSession, isChosenAttachSession, readAttachSessionId, type AttachProps } from "./attachSession";
import { readProductDraftScenario, saveProductDraftScenario } from "./draftStorage";
import { callSafely } from "./callSafely";
import styles from "../../components/cardStack.module.css";

type SelectionScenario = { productId: string; scenarioId: string; draft?: unknown };
export type ProductSelection =
  | { kind: "form" | "pending"; scenarioId: string }
  | { kind: "session"; scenarioId: string; sessionId: string };
type SelectionState =
  | { kind: "ready"; selection: ProductSelection }
  | { kind: "loading" | "error" }
  | { kind: "unavailable" | "identity-missing"; sessionId: string };
const terminal = (session: ScenarioSession) =>
  session.status === "completed" || session.status === "failed" || session.status === "expired";

/** Resolve the mode and attachment once, before the runtime restores a form or starts polling. */
export function useProductSelection(client: PlatformApiClient, scenarios: readonly SelectionScenario[], attach: AttachProps) {
  const [state, setState] = useState<SelectionState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const latest = useRef({ scenarios, attach });
  latest.current = { scenarios, attach };
  const controllerRef = useRef<AbortController | null>(null);
  const { attachSessionId, attachFromUrl } = attach;

  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    const { scenarios, attach } = latest.current;
    const productId = scenarios[0].productId;
    const persistence = getPaidPersistence(client);
    const current = () => !controller.signal.aborted && (!client.portalIdentity || client.portalIdentity.isCurrent());
    if (!current()) return;
    const savedChoice = readProductDraftScenario(productId, client.portalIdentity?.owner);
    const saved = scenarios.find((s) => s.draft && s.scenarioId === savedChoice);
    const remembered = readAttachSessionId(productId);
    const incoming = !attachFromUrl && remembered && isChosenAttachSession(productId, remembered) ? remembered : attachSessionId;
    const chosen = incoming !== undefined && isChosenAttachSession(productId, incoming);
    let recovery: ReturnType<typeof readPaidStartRecovery> = null;
    let recoveryBasis: string | undefined;
    try {
      recovery = persistence ? readPaidStartRecovery(persistence, productId) : null;
      recoveryBasis = JSON.stringify(recovery);
    } catch {
      // An explicit read is still allowed; the runtime refuses new sends with unreadable recovery.
      if (!attachFromUrl) {
        setState({ kind: "ready", selection: { kind: "form", scenarioId: (saved ?? scenarios[0]).scenarioId } });
        return;
      }
    }
    function unchanged() {
      if (!current()) return false;
      try {
        if ((recoveryBasis !== undefined && JSON.stringify(persistence ? readPaidStartRecovery(persistence, productId) : null) !== recoveryBasis) ||
          readProductDraftScenario(productId, client.portalIdentity?.owner) !== savedChoice ||
          readAttachSessionId(productId) !== remembered ||
          (incoming !== undefined && isChosenAttachSession(productId, incoming)) !== chosen) {
          setAttempt((previous) => previous + 1);
          return false;
        }
      } catch { setState({ kind: "error" }); return false; }
      return true;
    }
    function ready(selection: ProductSelection, explicit = false) {
      if (!unchanged()) return;
      if (selection.kind === "session" && explicit) {
        if (scenarios.find((s) => s.scenarioId === selection.scenarioId)?.draft) {
          saveProductDraftScenario(productId, selection.scenarioId, client.portalIdentity?.owner);
        }
        callSafely(() => attach.onAttachResolved?.(selection.sessionId));
      }
      setState({ kind: "ready", selection });
    }
    async function load(sessionId: string, allowMissing = false) {
      const result = await getScenarioSession(client, sessionId, { signal: controller.signal });
      if (!unchanged()) return null;
      if (!result.ok) {
        // A missing older recovery cannot block another explicitly selected result.
        // Undefined permits that fallback; null stops resolution on every other failure.
        if (allowMissing && result.error.type === "backend_error" && result.error.status === 404) return undefined;
        setState(result.error.type === "backend_error" && result.error.status === 404
          ? { kind: "unavailable", sessionId } : { kind: "error" });
        return null;
      }
      const scenarioId = result.value.scenarioId;
      if (scenarioId === undefined || !scenarios.some((s) => s.scenarioId === scenarioId)) {
        setState({ kind: result.value.scenarioId === undefined ? "identity-missing" : "unavailable", sessionId });
        return null;
      }
      return { ...result.value, scenarioId };
    }
    async function resolve() {
      if (attachFromUrl && incoming) {
        const session = await load(incoming);
        if (!session) return;
        ready({ kind: "session", sessionId: incoming, scenarioId: session.scenarioId }, true);
        return;
      }
      if (recovery?.kind === "pending") {
        if (scenarios.some((s) => s.scenarioId === recovery.scenarioId)) {
          ready({ kind: "pending", scenarioId: recovery.scenarioId });
        } else setState({ kind: "error" });
        return;
      }
      // Single-mode pages need no extra read unless a chosen result competes with paid recovery.
      // Their existing poll verifies the result; multi-mode pages must first resolve its scenario.
      if (scenarios.length === 1 && (!recovery || recovery.scenarioId === scenarios[0].scenarioId) &&
        !(recovery && chosen && recovery.scenarioSessionId !== incoming)) {
        const sessionId = recovery?.kind === "accepted" ? recovery.scenarioSessionId : incoming;
        ready(sessionId ? { kind: "session", sessionId, scenarioId: scenarios[0].scenarioId }
          : { kind: "form", scenarioId: scenarios[0].scenarioId });
        return;
      }
      let accepted: Awaited<ReturnType<typeof load>> = null;
      if (recovery?.kind === "accepted") {
        accepted = await load(recovery.scenarioSessionId, chosen && incoming !== recovery.scenarioSessionId);
        if (accepted === null) return;
        if (accepted && !terminal(accepted)) {
          ready({ kind: "session", sessionId: recovery.scenarioSessionId, scenarioId: accepted.scenarioId });
          return;
        }
      }
      const sessionId = chosen ? incoming : recovery?.kind === "accepted" ? recovery.scenarioSessionId : incoming;
      if (!sessionId) {
        ready({ kind: "form", scenarioId: (saved ?? scenarios[0]).scenarioId });
        return;
      }
      const session = accepted && recovery?.kind === "accepted" && sessionId === recovery.scenarioSessionId
        ? accepted : await load(sessionId);
      if (!session) return;
      const directGuestAttachment = !persistence && incoming !== undefined && incoming !== remembered;
      if (terminal(session) && !chosen && !directGuestAttachment && saved && saved.scenarioId !== session.scenarioId) {
        ready({ kind: "form", scenarioId: saved.scenarioId });
      } else {
        ready({ kind: "session", sessionId, scenarioId: session.scenarioId }, chosen);
      }
    }
    void resolve();
    return () => controller.abort();
  }, [client, attachSessionId, attachFromUrl, attempt]);

  function selectForm(scenarioId: string) {
    if (client.portalIdentity && !client.portalIdentity.isCurrent()) return;
    controllerRef.current?.abort();
    const scenario = latest.current.scenarios.find((s) => s.scenarioId === scenarioId)!;
    if (scenario.draft) saveProductDraftScenario(scenario.productId, scenarioId, client.portalIdentity?.owner);
    // A protected running operation may have temporarily hidden an older explicit result.
    // Choosing a form now also leaves that old choice; background accepted sessions stay recoverable.
    if (client.portalIdentity) forgetChosenAttachSession(scenario.productId);
    if (state.kind === "ready" && state.selection.kind === "session") {
      const sessionId = state.selection.sessionId;
      callSafely(() => latest.current.attach.onAttachEnd?.(sessionId));
    }
    setState({ kind: "ready", selection: { kind: "form", scenarioId } });
  }
  function discard() {
    if (state.kind !== "unavailable" && state.kind !== "identity-missing") return;
    const productId = latest.current.scenarios[0].productId;
    const persistence = getPaidPersistence(client);
    if (client.portalIdentity && !client.portalIdentity.isCurrent()) return;
    let nextRecovery: ReturnType<typeof readPaidStartRecovery> = null;
    try {
      const recovery = persistence ? readPaidStartRecovery(persistence, productId) : null;
      if (persistence && recovery?.kind === "accepted" && recovery.scenarioSessionId === state.sessionId) {
        clearPaidStartRecovery(persistence.storage, productId);
      } else nextRecovery = recovery;
    } catch { setState({ kind: "error" }); return; }
    forgetAttachSession(productId, state.sessionId);
    callSafely(() => latest.current.attach.onAttachDiscard?.(state.sessionId));
    controllerRef.current?.abort();
    if (nextRecovery) {
      retry();
    } else setState({ kind: "ready", selection: { kind: "form", scenarioId: latest.current.scenarios[0].scenarioId } });
  }
  function retry() { setState({ kind: "loading" }); setAttempt((value) => value + 1); }
  return { state, selectForm, discard, retry };
}

export function ProductSelectionStatus({ selection }: { selection: ReturnType<typeof useProductSelection> }) {
  const th = useHostT();
  const t = useProductT();
  const { state, retry, discard } = selection;
  if (state.kind === "loading") return <p role="status">{th("loading", { product: t("title") })}</p>;
  if (state.kind === "error") return <ErrorState message={th("errors.connectionLost")} onRetry={retry} />;
  if (state.kind === "ready") return null;
  return <Card className={styles.stack}>
    <ErrorState message={th(state.kind === "identity-missing" ? "errors.attachmentUnrecognized" : "errors.attachmentUnavailable")}
      onRetry={state.kind === "identity-missing" ? retry : undefined} embedded />
    <Button variant="secondary" onClick={discard}>{th("workspace.newTask")}</Button>
  </Card>;
}
