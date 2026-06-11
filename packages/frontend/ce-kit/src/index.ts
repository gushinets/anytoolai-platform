export type ScenarioStartRequest = {
  productId: string;
  scenarioId: string;
  input: unknown;
};

export async function createGuestIdentity(): Promise<{ guestId: string }> {
  return { guestId: "guest_demo" };
}

export async function getRuntimeConfig(productId: string): Promise<{ productId: string }> {
  return { productId };
}

export async function startScenario(_request: ScenarioStartRequest): Promise<{ scenarioSessionId: string }> {
  return { scenarioSessionId: "ssn_demo" };
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
