// English is the semantic source of truth for every host key; the other locale files are typed
// `Shape<typeof en>`. Apostrophes are safe in ICU unless directly followed by `{` -- translators
// use the typographic ’ everywhere so a placeholder is never swallowed by ICU quoting.
export const en = {
  language: { label: "Language" },
  nav: {
    label: "Tools",
    allTools: "All tools",
    runInProgress: "A run is in progress. If you leave now, it will continue; a successful result uses one run.",
  },
  loading: "Loading {product}…",
  unavailable: "{product} is unavailable right now. Please reload the page.",
  quotaReserved: "Available now: {available}. In progress: {reserved}.",
  quotaExhausted: "You've used all your {product} runs for now.",
  resultFetchFailed: "Your result is ready, but we couldn't load it. Please try again.",
  starting: "Starting…",
  generating: "Generating…",
  identityUnavailable: "We couldn't verify your identity. Please reload the page and try again.",
  retry: "Try again",
  // Code review finding: the product's own submit form had no accessible name of its own in any
  // non-English locale (a bare `${title} form` template with "form" hardcoded), so a screen reader
  // announced e.g. "ProposalAI form" even at a Russian locale.
  formLabel: "{product} form",
  workspace: {
    inputTitle: "Your details",
    previousDetails: "Created from previous details",
    backToInputs: "Back to details",
    newTask: "New task",
    handoffOpening: "Opening the next step…",
    handoffStay: "Stay on this page",
    handoffFailed: "Could not open the next step. Please try again.",
  },
  errors: {
    attachmentUnrecognized: "We couldn’t restore this saved session. Try again, or choose New task to open an empty form.",
    attachmentUnavailable: "This session cannot be opened in this tool. Choose New task to open an empty form.",
    quotaCapacityReserved: "Capacity is temporarily in use. Please try again shortly.",
    startFailed: "Could not start {product}. Please try again.",
    timeout: "This is taking longer than expected. Please try again.",
    connectionLost: "Lost connection while waiting for your result. Please try again.",
    tryAgain: "Please try again.",
  },
  result: {
    copy: "Copy",
    copying: "Copying…",
    copied: "Copied",
    copyFailed: "Could not copy to clipboard. Please copy the text above manually.",
    selectText: "Select text",
  },
  // Code review finding: `{field}` is a product-owned label of arbitrary grammatical number (e.g.
  // "Progress notes"), so no message here may make it the subject of a verb that agrees with number
  // ("is"/"are", French "est"/"sont", German "ist"/"sind", ...) -- every message is a label-colon-
  // fragment instead, which needs no agreement in any of the seven locales.
  validation: {
    required: "{field}: required.",
    maxLength: "{field}: {maxLength, plural, one {# character} other {# characters}} maximum.",
  },
};
