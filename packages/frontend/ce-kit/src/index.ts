export { PlatformApiClient } from "./api/client";
export type {
  PlatformApiClientOptions,
  PlatformApiMethod,
  PlatformApiRequestOptions,
  PlatformApiResult,
  PlatformApiRetryPolicy,
} from "./api/client";
export type { PlatformApiError } from "./api/errors";
export { networkError } from "./api/errors";
export {
  isGuestIdentityNotFound,
  isHandoffAcceptanceFailed,
  isHandoffAcceptanceSourceInvalid,
  isHandoffActionRefetchable,
  isHandoffExpired,
  isHandoffGuestIdentityInvalid,
  isHandoffNotActionable,
  isHandoffNotFound,
  isHandoffSourceInvalid,
  isHandoffTargetSchemaInvalid,
  isIdempotencyKeyConflict,
  isQuotaExhausted,
  isResultNotFound,
  isResultUnavailable,
  isScenarioActionConflict,
} from "./api/errors";
export { createInMemoryAsyncStorage } from "./storage/inMemoryAsyncStorage";
export type { AsyncStorage } from "./storage/asyncStorage";
export { createChromeStorageAdapter } from "./storage/chromeStorageAdapter";
export type { ChromeStorageArea } from "./storage/chromeStorageAdapter";
export { createLocalStorageAdapter, createWindowLocalStorageAdapter } from "./storage/localStorageAdapter";

export { DEFAULT_GUEST_STORAGE_KEY } from "./identity/guestIdentity";
export type { GuestIdentity, GuestIdentityOptions, GuestIdentityResult } from "./identity/guestIdentity";
export { refreshGuestIdentity } from "./identity/refreshGuestIdentity";
export type { RefreshGuestIdentityOptions } from "./identity/refreshGuestIdentity";
export { getQuota } from "./quota/getQuota";
export type { QuotaRequest, QuotaState } from "./quota/types";
export { isQuotaDimension, isQuotaPeriod, isQuotaUnit } from "./quota/quotaEnums";
export type { QuotaDimension, QuotaPeriod, QuotaUnit } from "./quota/quotaEnums";
export { generateIdempotencyKey } from "./scenarios/idempotencyKey";
export { startScenario } from "./scenarios/startScenario";
export { prepareScenarioStart } from "./scenarios/prepareScenarioStart";
export type {
  PreparedScenarioStart,
  PreparedScenarioStartExecuteOptions,
} from "./scenarios/prepareScenarioStart";
export { getScenarioSession } from "./scenarios/getScenarioSession";
export type { GetScenarioSessionOptions } from "./scenarios/getScenarioSession";
export { pollScenarioSession } from "./scenarios/pollScenarioSession";
export type {
  PollScenarioSessionOptions,
  PollScenarioSessionResult,
  PollScenarioSessionStopReason,
} from "./scenarios/pollScenarioSession";
export { nextAction } from "./scenarios/nextAction";
export type { NextActionOptions, NextActionRequest } from "./scenarios/nextAction";
export {
  COPY_RESULT_NEXT_ACTION_ID,
  copyResultAndRecordActivation,
} from "./scenarios/copyResultAndRecordActivation";
export type {
  CopyResultAndRecordActivationRequest,
  CopyResultAndRecordActivationResult,
} from "./scenarios/copyResultAndRecordActivation";
export type {
  ScenarioSession,
  ScenarioSessionSnapshot,
  ScenarioStartRequest,
} from "./scenarios/types";
export { isScenarioSessionStatus } from "./scenarios/scenarioSessionStatus";
export type { ScenarioSessionStatus } from "./scenarios/scenarioSessionStatus";

export { trackClientEvent } from "./events/trackClientEvent";
export type {
  ClientEventProperties,
  TrackClientEventOptions,
  TrackClientEventRequest,
} from "./events/trackClientEvent";
export type { ClientEventReceipt } from "./events/parseClientEventResponse";
export { isWebClientEventType } from "./events/webClientEventType";
export type { WebClientEventType } from "./events/webClientEventType";
export {
  DEFAULT_WEB_SESSION_STORAGE_KEY,
  WEB_SESSION_INACTIVITY_TIMEOUT_MS,
  getOrCreateWebSessionId,
} from "./events/webSession";
export type { WebSessionOptions } from "./events/webSession";

export { getRuntimeConfig, isFrontendType } from "./runtime";
export type {
  FrontendType,
  RuntimeConfig,
  RuntimeFrontend,
  RuntimeQuotaSummary,
  RuntimeRendererHint,
  RuntimeScenario,
} from "./runtime";

export { getResult } from "./results/getResult";
export type { GetResultOptions } from "./results/getResult";
export type { ResultArtifact } from "./results/types";

export { createHandoff } from "./handoffs/createHandoff";
export type { CreateHandoffOptions } from "./handoffs/createHandoff";
export { getHandoff } from "./handoffs/getHandoff";
export type { GetHandoffOptions } from "./handoffs/getHandoff";
export { acceptHandoff } from "./handoffs/acceptHandoff";
export type { AcceptHandoffOptions } from "./handoffs/acceptHandoff";
export { declineHandoff } from "./handoffs/declineHandoff";
export type { DeclineHandoffOptions } from "./handoffs/declineHandoff";
export type {
  AcceptHandoffRequest,
  CreateHandoffRequest,
  HandoffCreated,
  HandoffPreview,
} from "./handoffs/types";
export { isHandoffStatus } from "./handoffs/handoffStatus";
export type { HandoffStatus } from "./handoffs/handoffStatus";
export { openHandoffConsent } from "./handoffs/openHandoffConsent";
export type { OpenHandoffConsentOptions } from "./handoffs/openHandoffConsent";
export type { Navigate } from "./handoffs/navigation";
export { createWindowNavigator } from "./handoffs/windowNavigator";
export { createChromeTabNavigator } from "./handoffs/chromeTabNavigator";
export type { ChromeTabsArea } from "./handoffs/chromeTabNavigator";

export function renderQuotaState(status: string): { status: string } {
  return { status };
}

export function renderJobStatus(status: string): { status: string } {
  return { status };
}

export function renderError(errorCode: string): { errorCode: string } {
  return { errorCode };
}
