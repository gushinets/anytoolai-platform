import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { persistPaidStartRecovery, readPaidStartRecovery } from "@anytoolai/ce-kit";
import { createPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, installPortalSession, requirePortalAuthorization } from "../src/lib/portalSession";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { testProductDefinition, TEST_PRODUCT_IDS, TEST_PRODUCT_MESSAGES_EN } from "./fixtures/testProductDefinition";
import { errorResponse, resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales(TEST_PRODUCT_MESSAGES_EN));
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const request = { ...TEST_PRODUCT_IDS, frontendId: "web_mirror", input: { text: "Frozen original input" } };
const fetcher = vi.fn<typeof fetch>();
const starts: RequestInit[] = [];
const paths: string[] = [];

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/products/test_product");
  requirePortalAuthorization(true);
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner, accessToken: "t".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  starts.length = 0;
  paths.length = 0;
  fetcher.mockReset();
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function setup(
  kind: "pending" | "accepted", runtime: () => Response,
  output: Record<string, unknown> = {}, failure?: "start" | "poll",
) {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, kind === "pending"
    ? { version: 1, kind, owner, ...TEST_PRODUCT_IDS, idempotencyKey: "original_key", request }
    : { version: 1, kind, owner, ...TEST_PRODUCT_IDS, scenarioSessionId: "session_1" });
  let polls = 0;
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    paths.push(path);
    if (path.endsWith("runtime-config")) return runtime();
    if (path.endsWith("/start")) {
      starts.push(init!);
      if (failure === "start" && starts.length <= 2) throw new TypeError("Lost start response");
      return startResponse();
    }
    if (path.startsWith("/v1/scenario-sessions/")) {
      if (failure === "poll" && polls++ === 0) return errorResponse(503, "temporarily_unavailable");
      return sessionResponse();
    }
    if (path.startsWith("/v1/results/")) return resultResponse(TEST_PRODUCT_IDS, output);
    throw new Error("Unexpected request: " + path);
  });
  return { client, persistence };
}

const unavailable = [
  { name: "disabled product", runtime: () => errorResponse(404, "product_not_found") },
  { name: "unavailable config", runtime: () => errorResponse(503, "runtime_unavailable") },
  { name: "removed scenario", runtime: () => runtimeConfigResponse(TEST_PRODUCT_IDS, { scenarios: [] }) },
  { name: "disabled frontend", runtime: () => runtimeConfigResponse(TEST_PRODUCT_IDS, {
    frontends: [{ frontend_id: "web_mirror", type: "web", enabled: false }],
  }) },
];

it.each(["pending", "accepted"] as const)("recovers %s with available config (control)", async (kind) => {
  const { client } = setup(kind, () => runtimeConfigResponse(TEST_PRODUCT_IDS));
  render(<ProductRunPage client={client} definition={testProductDefinition} />);
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
});

it.each(unavailable.flatMap((config) => (["pending", "accepted"] as const).map((kind) => ({ ...config, kind }))))(
  "recovers $kind with $name without enabling a new run", async ({ kind, runtime }) => {
    const { client, persistence } = setup(kind, runtime);
    render(<ProductRunPage client={client} definition={testProductDefinition} />);
    await screen.findByText("Generated result text.");
    expect(paths).toContain("/v1/scenario-sessions/session_1");
    expect(paths).toContain("/v1/results/result_1");
    expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
    if (kind === "pending") {
      expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
      const body = starts[0].body;
      if (typeof body !== "string") throw new Error("Expected the original JSON request");
      const submitted: unknown = JSON.parse(body);
      expect(submitted).toMatchObject({ input: request.input });
    }
    expect(readPaidStartRecovery(persistence, TEST_PRODUCT_IDS.productId)).toMatchObject({ kind: "accepted", scenarioSessionId: "session_1" });
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Run" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "New task" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.submit(screen.getByRole("form"));
    expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
  },
);

it.each((["pending", "accepted"] as const).flatMap((kind) => [
  { kind, output: { schema_ref: "another_product.output_v1" } },
  { kind, output: { schema_version: 2 } },
]))("rejects an incompatible result when restoring $kind without config: $output", async ({ kind, output }) => {
  const { client } = setup(kind, () => errorResponse(404, "product_not_found"), output);
  render(<ProductRunPage client={client} definition={testProductDefinition} />);
  await screen.findByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed);
  expect(screen.queryByText("Generated result text.")).toBeNull();
});

it("keeps an unavailable product closed without an existing operation", async () => {
  fetcher.mockResolvedValue(errorResponse(404, "product_not_found"));
  render(<ProductRunPage client={createPlatformApiClient()} definition={testProductDefinition} />);
  await screen.findByText("Test Product is unavailable right now. Please reload the page.");
  expect(screen.queryByLabelText("Text")).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it.each(["pending", "accepted"] as const)("can retry a failed %s recovery without config", async (kind) => {
  const { client } = setup(kind, () => errorResponse(404, "product_not_found"), {}, kind === "pending" ? "start" : "poll");
  render(<ProductRunPage client={client} definition={testProductDefinition} />);
  fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(kind === "pending" ? 3 : 0);
  if (kind === "pending") {
    expect(new Set(starts.map((start) => new Headers(start.headers).get("Idempotency-Key")))).toEqual(new Set(["original_key"]));
    expect(new Set(starts.map((start) => start.body)).size).toBe(1);
  } else {
    expect(paths.filter((path) => path.startsWith("/v1/scenario-sessions/"))).toEqual([
      "/v1/scenario-sessions/session_1", "/v1/scenario-sessions/session_1",
    ]);
  }
});

it("opens an explicitly selected result without config and preserves another pending operation", async () => {
  const { client, persistence } = setup("pending", () => errorResponse(404, "product_not_found"));
  const pending = readPaidStartRecovery(persistence, TEST_PRODUCT_IDS.productId);
  render(<ProductRunPage client={client} definition={testProductDefinition} attachSessionId="session_1" attachFromUrl />);
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(0);
  expect(readPaidStartRecovery(persistence, TEST_PRODUCT_IDS.productId)).toEqual(pending);
});
