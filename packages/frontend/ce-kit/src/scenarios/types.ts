export type ScenarioStartRequest = {
  productId: string;
  scenarioId: string;
  frontendId: string;
  input: unknown;
  guestId?: string;
  userId?: string;
  sourceFrontendInstanceId?: string;
};

/** Backend-owned scenario session snapshot, safe for CE-kit consumers. */
export type ScenarioSessionSnapshot = {
  scenarioSessionId: string;
  jobId: string | null;
  status: string;
  allowedNextActions: string[];
  resultArtifactId: string | null;
};

/**
 * `GET /v1/scenario-sessions/{id}` response: the same session snapshot plus the checkpoint the
 * frontend must echo back on `nextAction()`.
 */
export type ScenarioSession = ScenarioSessionSnapshot & {
  currentCheckpointId: string | null;
};
