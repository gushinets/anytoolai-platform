export const productConfig = {
  productId: "kernel_demo",
  frontendId: "kernel_demo_ce",
  defaultScenarioId: "kernel_demo.single_action_smoke_v1",
  // configs/kernel/products/kernel_demo/{scenarios,handoffs}.yaml: the ANY-224 self-handoff smoke
  // journey (source scenario -> consent -> linked target session), distinct from the general
  // single-action journey above.
  handoffSourceScenarioId: "kernel_demo.handoff_smoke_source_v1",
  handoffDefinitionId: "kernel_demo_source_to_target_v1",
};
