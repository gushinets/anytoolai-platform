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
  /**
   * The checkpoint the copy button is shown against; the backend is authoritative on staleness.
   * `null` when the completed session has no active checkpoint to record an activation against
   * (legitimately nullable -- see `ProductRunPageProps`'s own `Phase["result"]` docstring) -- the
   * clipboard write still happens, only the next-action recording is skipped, so callers no longer
   * need their own separate no-checkpoint branch.
   */
  checkpointId: string | null;
  /**
   * Performs the actual clipboard write (typically `(text) => navigator.clipboard.writeText(text)`).
   * Injected rather than called directly so the ordering contract below is testable without a
   * DOM, and so a host can substitute a fallback (execCommand, a native bridge) without CE-kit
   * knowing about it. A rejection means the copy did not happen.
   */
  writeToClipboard: (text: string) => Promise<void>;
  /**
   * Fired the instant the clipboard write succeeds, before the (network-bound) activation record
   * is even started. Lets a caller show "Copied" immediately instead of waiting on the record's
   * round-trip -- code review finding: awaiting this whole function before flipping the UI to
   * "Copied" regressed the previous fire-and-forget UX. Never awaited by this function itself; a
   * throwing handler is the caller's own bug, not something this function should protect against.
   */
  onCopied?: () => void;
};

export type CopyResultAndRecordActivationResult =
  /** The clipboard write failed; no activation was recorded, because nothing was copied. */
  | { copied: false; reason: unknown }
  /**
   * The clipboard write succeeded. `activation` is the outcome of recording it, or `null` when
   * `checkpointId` was `null` and no recording was attempted. A failed activation request does not
   * revoke the copy -- the text is already on the clipboard, and the platform contract explicitly
   * allows this metric to undercount.
   */
  | { copied: true; activation: PlatformApiResult<ScenarioSession> | null };

/**
 * The shared copy-button activation contract (ANY-17, design spec "ProposalAI activation"): the
 * clipboard write completes first, and only then is exactly one `copy_result` next-action
 * recorded for *this call*, producing `client.next_action_clicked(copy_result)` on the backend --
 * provided there is a checkpoint to record it against (`checkpointId !== null`). With a `null`
 * checkpoint the copy still succeeds but nothing is recorded, and `activation` is `null`. A failed
 * clipboard write records nothing; a failed activation request never revokes a successful copy.
 *
 * This is per-call exactly-once, not per-session: the backend's checkpoint validation
 * (`validate_next_action()`) only checks that the supplied checkpoint is still current -- it does
 * not consume the action or advance the checkpoint, so a second copy click against the same
 * still-actionable session emits a second raw `client.next_action_clicked(copy_result)` event. Per
 * the design spec, the `activation` metric itself is what dedupes -- it counts *distinct*
 * `scenario_session_id` values that produced the event, not raw event rows -- so a repeat click
 * doesn't inflate activation, even though it does add another row to the event log.
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
  request.onCopied?.();
  if (!request.checkpointId) {
    return { copied: true, activation: null };
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
