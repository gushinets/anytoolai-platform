// ANY-521 gave ProposalAI its own tone labels ("Warm & personable" etc.), distinct from the shared
// neutral|warm|firm word labels Client Update Writer still uses -- this product intentionally does
// not import `products/shared/toneMessages` (its own exec-plan: "no speculative shared RadioGroup
// abstraction for one product"). Wire values (`toneOptions`' keys, sent as-is) stay neutral|warm|firm.
export const en = {
  title: "ProposalAI",
  description: "Turn a client brief and your relevant strengths into a proposal ready to send.",
  quotaRemaining: "{remaining} of {limit, plural, one {# proposal} other {# proposals}} remaining.",
  fields: {
    taskText: "Describe the task",
    taskTextPlaceholder: "Paste the client's task, brief, or job post.",
    taskTextHelp: "Include the goal, deliverables, constraints, and timeline when available.",
    freelancerPositioning: "Your positioning",
    freelancerPositioningPlaceholder: "Describe the experience and strengths that make you a good fit.",
    freelancerPositioningHelp: "Use only claims you can stand behind—the proposal will not invent experience.",
    toneLegend: "Proposal style",
  },
  toneOptions: {
    warm: "Warm & personable",
    neutral: "Clear & professional",
    firm: "Confident & direct",
  },
  // Names used inside validation messages ("{field}: required."), which read differently from the
  // input labels above.
  fieldNames: {
    taskText: "Task description",
    freelancerPositioning: "Your positioning",
  },
  generate: {
    submit: "Generate proposal",
    running: "Generating your proposal…",
    runFailed: "Something went wrong generating your proposal. Please try again.",
    startAnother: "Create another proposal",
  },
};
