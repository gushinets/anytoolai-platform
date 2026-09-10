import type { PlatformApiClient, PlatformApiResult } from "../api/client";
import { nextAction } from "./nextAction";
import type { NextActionOptions } from "./nextAction";
import type { ScenarioSession } from "./types";

/** The next-action id every copy-button activation records, across products. */
export const COPY_RESULT_NEXT_ACTION_ID = "copy_result";

export type CopyResultAndRecordActivationRequest = {
  /** The result text to place on the clipboard. */
  text: string;
  scenarioSessionId: string;
  /** The checkpoint the copy button is shown against; the backend is authoritative on staleness. */
  checkpointId: string;
  /**
   * Performs the actual clipboard write (typically `(text) => navigator.clipboard.writeText(text)`).
   * Injected rather than called directly so the ordering contract below is testable without a
   * DOM, and so a host can substitute a fallback (execCommand, a native bridge) without CE-kit
   * knowing about it. A rejection means the copy did not happen.
   */
  writeToClipboard: (text: string) => Promise<void>;
};

export type CopyResultAndRecordActivationResult =
  /** The clipboard write failed; no activation was recorded, because nothing was copied. */
  | { copied: false; reason: unknown }
  /**
   * The clipboard write succeeded. `activation` is the outcome of recording it; a failed
   * activation request does not revoke the copy -- the text is already on the clipboard, and the
   * platform contract explicitly allows this metric to undercount.
   */
  | { copied: true; activation: PlatformApiResult<ScenarioSession> };

/**
 * The shared copy-button activation contract (ANY-17, design spec "ProposalAI activation"): the
 * clipboard write completes first, and only then is exactly one `copy_result` next-action
 * recorded for this call, producing `client.next_action_clicked(copy_result)` on the backend. A
 * failed clipboard write records nothing; a failed activation request never revokes a successful
 * copy. Per-session exactly-once is the backend's checkpoint validation, not a client concern.
 *
 * Never throws for the activation request (`nextAction()` reports failure as `{ ok: false }`);
 * a clipboard rejection is caught and reported as `{ copied: false }`.
 */
export async function copyResultAndRecordActivation(
  client: PlatformApiClient,
  request: CopyResultAndRecordActivationRequest,
  options?: NextActionOptions,
): Promise<CopyResultAndRecordActivationResult> {
  try {
    await request.writeToClipboard(request.text);
  } catch (reason: unknown) {
    return { copied: false, reason };
  }
  const activation = await nextAction(
    client,
    {
      scenarioSessionId: request.scenarioSessionId,
      nextActionId: COPY_RESULT_NEXT_ACTION_ID,
      checkpointId: request.checkpointId,
    },
    options,
  );
  return { copied: true, activation };
}
