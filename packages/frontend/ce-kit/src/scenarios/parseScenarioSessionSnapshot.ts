import type { ScenarioSession, ScenarioSessionSnapshot } from "./types";

function _isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function _isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/**
 * Validates and maps the backend's `ScenarioStartResponse` / `ScenarioSessionResponse` payload
 * (snake_case) into the client's `ScenarioSessionSnapshot` shape (camelCase). Both response
 * models share this same core shape; `ScenarioSessionResponse` additionally carries
 * `current_checkpoint_id`, which callers that need it read separately. Returns null for anything
 * that doesn't match, so callers fall back to `invalid_response` instead of trusting arbitrary
 * payload content.
 */
export function parseScenarioSessionSnapshot(payload: unknown): ScenarioSessionSnapshot | null {
  if (!_isRecord(payload)) {
    return null;
  }

  const {
    scenario_session_id: scenarioSessionId,
    job_id: jobId,
    status,
    allowed_next_actions: allowedNextActions,
    result_artifact_id: resultArtifactId,
  } = payload;

  if (
    typeof scenarioSessionId !== "string" ||
    typeof status !== "string" ||
    !_isStringArray(allowedNextActions)
  ) {
    return null;
  }
  if (jobId !== null && jobId !== undefined && typeof jobId !== "string") {
    return null;
  }
  if (resultArtifactId !== null && resultArtifactId !== undefined && typeof resultArtifactId !== "string") {
    return null;
  }

  return {
    scenarioSessionId,
    jobId: jobId ?? null,
    status,
    allowedNextActions,
    resultArtifactId: resultArtifactId ?? null,
  };
}

/**
 * Validates and maps the backend's `ScenarioSessionResponse` payload (snake_case) into the
 * client's `ScenarioSession` shape (camelCase) -- the session snapshot plus the checkpoint id
 * `nextAction()` must echo back.
 */
export function parseScenarioSession(payload: unknown): ScenarioSession | null {
  const snapshot = parseScenarioSessionSnapshot(payload);
  if (!snapshot || !_isRecord(payload)) {
    return null;
  }

  const { current_checkpoint_id: currentCheckpointId } = payload;
  if (currentCheckpointId !== null && currentCheckpointId !== undefined && typeof currentCheckpointId !== "string") {
    return null;
  }

  return { ...snapshot, currentCheckpointId: currentCheckpointId ?? null };
}
