/**
 * `POST /v1/handoffs` request: mints a fresh handoff token for a definition, scoped to a source
 * scenario session and artifact. The backend is authoritative on whether that source is eligible.
 */
export type CreateHandoffRequest = {
  handoffDefinitionId: string;
  sourceScenarioSessionId: string;
  sourceArtifactId: string;
};

/**
 * `POST /v1/handoffs` response. `handoffToken` is the only response that ever carries the opaque
 * plaintext token -- treat it as a short-lived bearer capability, never log it or derive/inspect
 * its contents.
 */
export type HandoffCreated = {
  handoffId: string;
  handoffToken: string;
  status: string;
  expiresAt: string;
};
