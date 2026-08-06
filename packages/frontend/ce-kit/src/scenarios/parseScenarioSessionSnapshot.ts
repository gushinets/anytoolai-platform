import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isRecord, isStringArray } from "../api/parsing";
import type { ScenarioSession, ScenarioSessionSnapshot } from "./types";

/**
 * Validates and maps the backend's `ScenarioStartResponse` / `ScenarioSessionResponse` payload
 * (snake_case) into the client's `ScenarioSessionSnapshot` shape (camelCase). Both response
 * models share this same core shape; `ScenarioSessionResponse` additionally carries
 * `current_checkpoint_id`, which callers that need it read separately. Returns null for anything
 * that doesn't match, so callers fall back to `invalid_response` instead of trusting arbitrary
 * payload content.
 */
export function parseScenarioSessionSnapshot(payload: unknown): ScenarioSessionSnapshot | null {
  if (!isRecord(payload)) {
    return null;
  }

  const {
    scenario_session_id: scenarioSessionId,
    job_id: jobId,
    status,
    allowed_next_actions: allowedNextActions,
    result_artifact_id: resultArtifactId,
  } = payload;

  // `allowed_next_actions` is optional on the wire (both ScenarioSessionResponse and
  // ScenarioStartResponse declare it `allowed_next_actions?: string[]`) -- an absent key means
  // "no next actions", not a malformed payload.
  const allowedNextActionsAbsent = allowedNextActions === undefined;
  if (
    typeof scenarioSessionId !== "string" ||
    typeof status !== "string" ||
    (!allowedNextActionsAbsent && !isStringArray(allowedNextActions))
  ) {
    return null;
  }
  // `job_id` is a required (but nullable) property on both response models -- the key must be
  // present, unlike `allowed_next_actions` above. An absent key is malformed, not `null`.
  if (jobId !== null && typeof jobId !== "string") {
    return null;
  }
  if (resultArtifactId !== null && resultArtifactId !== undefined && typeof resultArtifactId !== "string") {
    return null;
  }

  return {
    scenarioSessionId,
    jobId,
    status,
    allowedNextActions: allowedNextActionsAbsent ? [] : allowedNextActions,
    resultArtifactId: resultArtifactId ?? null,
  };
}

/**
 * Validates and maps the backend's `ScenarioStartResponse` payload (snake_case) into the client's
 * `ScenarioSessionSnapshot` shape. Stricter than `parseScenarioSessionSnapshot()` above: unlike
 * `ScenarioSessionResponse.job_id` (nullable), the backend's `ScenarioStartResponse.job_id` is
 * required -- a start response always creates a job. A missing/null `job_id` here falls back to
 * `invalid_response` instead of silently returning `{ ok: true, value: { jobId: null, ... } }`.
 */
export function parseScenarioStartResponse(payload: unknown): ScenarioSessionSnapshot | null {
  const snapshot = parseScenarioSessionSnapshot(payload);
  if (!snapshot || snapshot.jobId === null) {
    return null;
  }
  return snapshot;
}

/**
 * Validates and maps the backend's `ScenarioSessionResponse` payload (snake_case) into the
 * client's `ScenarioSession` shape (camelCase) -- the session snapshot plus the checkpoint id
 * `nextAction()` must echo back.
 */
export function parseScenarioSession(payload: unknown): ScenarioSession | null {
  const snapshot = parseScenarioSessionSnapshot(payload);
  // `snapshot` is only non-null once `parseScenarioSessionSnapshot` has already confirmed
  // `isRecord(payload)`, so this narrows `payload`'s type without re-checking it.
  if (!snapshot || !isRecord(payload)) {
    return null;
  }

  const { current_checkpoint_id: currentCheckpointId } = payload;
  if (currentCheckpointId !== null && currentCheckpointId !== undefined && typeof currentCheckpointId !== "string") {
    return null;
  }

  return { ...snapshot, currentCheckpointId: currentCheckpointId ?? null };
}

// Compile-time drift checks: fail typecheck if either backend response schema grows, loses,
// retypes, or changes the nullability/optionality of a field the parsers above don't know about.
type _ScenarioSessionResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["ScenarioSessionResponse"],
  {
    allowed_next_actions?: string[];
    current_checkpoint_id?: string | null;
    job_id: string | null;
    result_artifact_id?: string | null;
    scenario_session_id: string;
    status: string;
  }
>;
const _assertScenarioSessionResponseShapeMatchesGenerated: _ScenarioSessionResponseShapeCheck = true;
void _assertScenarioSessionResponseShapeMatchesGenerated;

type _ScenarioStartResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["ScenarioStartResponse"],
  {
    allowed_next_actions?: string[];
    job_id: string;
    result_artifact_id?: string | null;
    scenario_session_id: string;
    status: string;
  }
>;
const _assertScenarioStartResponseShapeMatchesGenerated: _ScenarioStartResponseShapeCheck = true;
void _assertScenarioStartResponseShapeMatchesGenerated;
