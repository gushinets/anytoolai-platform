/**
 * `GET /v1/results/{result_artifact_id}` response: the normalized, frontend-safe canonical
 * workflow result. Never carries raw/debug artifacts or provider/model/provider-call fields --
 * the backend's `ResultService` rejects those before they ever reach this shape.
 */
export type ResultArtifact = {
  resultArtifactId: string;
  scenarioSessionId: string;
  jobId: string;
  workflowId: string;
  workflowVersion: number;
  schemaRef: string;
  schemaVersion: number;
  createdAt: string;
  output: Record<string, unknown>;
};