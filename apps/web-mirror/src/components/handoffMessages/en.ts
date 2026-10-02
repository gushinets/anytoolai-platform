// Handoff consent page copy (the backend owns the preview values; this is only the chrome around them).
export const en = {
  title: "Review handoff",
  loading: "Loading handoff…",
  notFound: "This handoff link is not valid.",
  loadFailed: "Something went wrong loading this handoff. Please try again.",
  retry: "Try again",
  actionFailed: "That action could not be completed. Please try again.",
  fields: {
    from: "From",
    to: "To",
    expires: "Expires",
    status: "Status",
  },
  // Shown on a spent (accepted/consumed) token that still names the queued target session.
  openResult: "Open result",
  accept: "Accept",
  decline: "Decline",
  accepting: "Accepting…",
  declining: "Declining…",
  status: {
    waiting: "Waiting for your decision",
    accepted: "Accepted",
    declined: "Declined",
    expired: "Expired",
    failed: "Failed",
  },
  // Labels for the backend's known preview keys (`handoffs.yaml` `preview_mapping`); any other key is shown as sent.
  previewFields: {
    summary: "Summary",
    missing_fields: "Missing details",
  },
};
