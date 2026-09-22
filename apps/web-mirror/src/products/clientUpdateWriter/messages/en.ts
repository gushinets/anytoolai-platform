import { en as tone } from "../../shared/toneMessages/en";

export const en = {
  title: "Client Update Writer",
  tone,
  // No quota policy is configured for this product yet; kept mode-agnostic for when one exists.
  quotaRemaining: "{remaining} of {limit, plural, one {# Client Update Writer run} other {# Client Update Writer runs}} remaining.",
  modes: {
    legend: "Mode",
    update: "Update",
    reply_draft: "Reply Draft",
    prepaid_request: "Prepaid Request",
  },
  fields: {
    progressNotes: "Progress notes",
    clientMessage: "Client message",
    replyGoal: "Reply goal",
    billingNotes: "Billing notes",
    billingAmount: "Amount",
    billingDueDate: "Due date (optional)",
    tone: "Tone",
    tonePlaceholder: "Select a tone",
  },
  // Names used inside validation messages ("{field} is required."); differ from the labels above
  // where a label carries a suffix such as "(optional)".
  fieldNames: {
    progressNotes: "Progress notes",
    clientMessage: "Client message",
    replyGoal: "Reply goal",
    billingNotes: "Billing notes",
    billingAmount: "Amount",
    billingDueDate: "Due date",
    tone: "Tone",
  },
  update: {
    submit: "Write update",
    running: "Writing your update…",
    runFailed: "Something went wrong writing your update. Please try again.",
  },
  reply_draft: {
    submit: "Write reply",
    running: "Writing your reply…",
    runFailed: "Something went wrong writing your reply. Please try again.",
  },
  prepaid_request: {
    submit: "Write request",
    running: "Writing your request…",
    runFailed: "Something went wrong writing your request. Please try again.",
  },
};
