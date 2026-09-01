import type { HandoffStatus } from "./handoffStatus";

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
  status: HandoffStatus;
  expiresAt: string;
};

/**
 * The backend safe preview shared by `GET /v1/handoffs/{token}`, `POST .../accept`, and `POST
 * .../decline` -- all three return the identical `HandoffPreviewResponse` shape. `preview` is a
 * bounded, config-mapped `dict[str, Any]` on the wire -- render it as opaque key/value pairs only,
 * never assume specific keys. `targetScenarioSessionId`/`targetJobId` are null until a handoff is
 * accepted.
 */
export type HandoffPreview = {
  handoffId: string;
  status: HandoffStatus;
  sourceProductId: string;
  sourceProductDisplayName: string;
  targetProductId: string;
  targetProductDisplayName: string;
  targetScenarioId: string;
  preview: Record<string, unknown>;
  expiresAt: string;
  targetScenarioSessionId: string | null;
  targetJobId: string | null;
};

/** `POST /v1/handoffs/{token}/accept` request body -- both fields are optional on the wire. */
export type AcceptHandoffRequest = {
  guestId?: string;
  sourceFrontendInstanceId?: string;
};
