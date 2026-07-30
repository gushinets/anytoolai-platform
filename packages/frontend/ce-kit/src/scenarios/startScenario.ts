export type ScenarioStartRequest = {
  productId: string;
  scenarioId: string;
  input: unknown;
};

export type ScenarioStartDemoResponse = {
  scenarioSessionId: string;
};

/**
 * A13 demo helper only.
 *
 * It does not call the Platform API and it does not propagate guest identity. A16 owns the real
 * shared Platform API client, including backend `POST /scenario/start`, `429 quota_exhausted`,
 * `422`, polling, and normalized frontend error handling.
 * TODO(A16, ANY-150): the real client must send an `Idempotency-Key` header on every start
 * request (same key on retry) so duplicate submits replay instead of double-charging quota --
 * see docs/architecture/scenario-session-model.md.
 */
export async function startScenario(
  _request: ScenarioStartRequest,
): Promise<ScenarioStartDemoResponse> {
  return { scenarioSessionId: "ssn_demo" };
}
