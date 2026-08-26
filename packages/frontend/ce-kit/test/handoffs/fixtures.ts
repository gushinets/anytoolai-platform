/** Shared `HandoffPreviewResponse` fixture for getHandoff/acceptHandoff/declineHandoff/parseHandoffPreview tests. */
export function handoffPreviewPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    handoff_id: "handoff_123",
    status: "created",
    source_product_id: "kernel_demo",
    source_product_display_name: "Kernel Demo",
    target_product_id: "freelancer_demo",
    target_product_display_name: "Freelancer Demo",
    target_scenario_id: "scenario_1",
    preview: { key: "value" },
    expires_at: "2026-01-01T00:10:00Z",
    target_scenario_session_id: null,
    target_job_id: null,
    ...overrides,
  };
}
