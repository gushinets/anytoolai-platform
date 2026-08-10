export { PlatformApiClient } from "./api/client";
export type {
  PlatformApiClientOptions,
  PlatformApiMethod,
  PlatformApiRequestOptions,
  PlatformApiResult,
  PlatformApiRetryPolicy,
} from "./api/client";
export type { PlatformApiError } from "./api/errors";
export {
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

export type { GuestIdentity, GuestIdentityOptions, GuestIdentityResult } from "./identity/guestIdentity";
export { getQuota } from "./quota/getQuota";
export type { QuotaRequest, QuotaState } from "./quota/types";
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
export type {
  ScenarioSession,
  ScenarioSessionSnapshot,
  ScenarioStartRequest,
} from "./scenarios/types";

export { getRuntimeConfig } from "./runtime";
export type {
  RuntimeConfig,
  RuntimeFrontend,
  RuntimeQuotaSummary,
  RuntimeRendererHint,
  RuntimeScenario,
} from "./runtime";

export { getResult } from "./results/getResult";
export type { GetResultOptions } from "./results/getResult";
export type { ResultArtifact } from "./results/types";

export async function pollJob(jobId: string): Promise<{ jobId: string; status: string }> {
  return { jobId, status: "succeeded" };
}

export async function getArtifact(artifactId: string): Promise<{ artifactId: string }> {
  return { artifactId };
}

export async function createHandoff(): Promise<{ handoffToken: string }> {
  return { handoffToken: "handoff_demo" };
}

export function openHandoffConsent(handoffToken: string): { url: string } {
  return { url: `/handoff/${handoffToken}` };
}

export async function captureEmail(email: string): Promise<{ email: string }> {
  return { email };
}

export function trackClientEvent(eventType: string, properties: Record<string, unknown> = {}) {
  return { eventType, properties };
}

export function renderQuotaState(status: string): { status: string } {
  return { status };
}

export function renderJobStatus(status: string): { status: string } {
  return { status };
}

export function renderError(errorCode: string): { errorCode: string } {
  return { errorCode };
}
