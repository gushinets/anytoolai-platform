export { createGuestIdentity } from "./identity/guestIdentity";
export type { GuestIdentity, GuestIdentityOptions } from "./identity/guestIdentity";
export { getQuota } from "./quota/getQuota";
export type { QuotaRequest } from "./quota/getQuota";
export { startScenario } from "./scenarios/startScenario";
export type {
  ScenarioStartDemoResponse,
  ScenarioStartRequest,
} from "./scenarios/startScenario";

export async function getRuntimeConfig(productId: string): Promise<{ productId: string }> {
  return { productId };
}

export async function pollJob(jobId: string): Promise<{ jobId: string; status: string }> {
  return { jobId, status: "succeeded" };
}

export async function getScenarioSession(
  scenarioSessionId: string,
): Promise<{ scenarioSessionId: string; status: string }> {
  return { scenarioSessionId, status: "completed" };
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
