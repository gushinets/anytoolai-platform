import { en as tone } from "../../shared/toneMessages/en";

export const en = {
  title: "ProposalAI",
  tone,
  quotaRemaining: "{remaining} of {limit, plural, one {# proposal} other {# proposals}} remaining.",
  fields: {
    taskText: "Describe the task",
    freelancerPositioning: "Your positioning",
    tone: "Tone (optional)",
    tonePlaceholder: "Default",
    language: "Language (optional)",
  },
  // Names used inside validation messages ("{field} is required."), which read differently from the
  // input labels above.
  fieldNames: {
    taskText: "Task description",
    freelancerPositioning: "Your positioning",
    language: "Language",
  },
  validation: { languageFormat: 'Language must look like "en" or "en-US".' },
  generate: {
    submit: "Generate proposal",
    running: "Generating your proposal…",
    runFailed: "Something went wrong generating your proposal. Please try again.",
  },
};
