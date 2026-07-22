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
 */
export async function startScenario(
  _request: ScenarioStartRequest,
): Promise<ScenarioStartDemoResponse> {
  return { scenarioSessionId: "ssn_demo" };
}
