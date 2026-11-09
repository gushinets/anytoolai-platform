// ProposalAI's descriptive tone labels differ from Client Update Writer's plain labels;
// wire values stay neutral|warm|firm in both products.
export const en = {
  title: "ProposalAI",
  description: "Turn a client brief and your relevant strengths into a proposal ready to send.",
  quotaRemaining: "{remaining} of {limit, plural, one {# proposal} other {# proposals}} remaining.",
  fields: {
    taskText: "Describe the task",
    taskTextPlaceholder: "Paste the client's task, brief, or job post.",
    taskTextHelp: "Include the goal, deliverables, constraints, and timeline when available.",
    freelancerPositioning: "Your experience and strengths",
    freelancerPositioningPlaceholder: "Describe the experience and strengths that make you a good fit.",
    freelancerPositioningHelp: "The proposal is built only from what you write here. Give checkable facts: tools, cases, results.",
    toneLegend: "Proposal style",
    required: "required",
    languageLabel: "Proposal language",
    languageHelp: "Not the interface language. By default the proposal is written in the language of the task.",
    languageAuto: "Same as the task",
    counterNear: "Approaching the limit of {max} characters.",
    counterOver: "Over the limit of {max} characters.",
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
    freelancerPositioning: "Your experience and strengths",
  },
  result: {
    gapsTitle: "Not covered by your experience",
    gapsHint: "The proposal does not claim these. Cover them yourself or leave them out.",
  },
  generate: {
    submit: "Generate proposal",
    running: "Generating your proposal…",
    runFailed: "Something went wrong generating your proposal. Please try again.",
    resultTitle: "Proposal",
    placeholder: "Your proposal will appear here after you generate it.",
    regenerate: "Regenerate proposal",
  },
};
