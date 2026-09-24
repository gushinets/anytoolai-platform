// English is the semantic source of truth for every host key; the other locale files are typed
// `Shape<typeof en>`. Apostrophes are safe in ICU unless directly followed by `{` -- translators
// use the typographic ’ everywhere so a placeholder is never swallowed by ICU quoting.
export const en = {
  language: { label: "Language" },
  nav: {
    label: "Tools",
    allTools: "All tools",
    runInProgress: "A run is in progress. If you leave now, you won’t see the result and the quota won’t be restored.",
  },
  loading: "Loading {product}…",
  unavailable: "{product} is unavailable right now. Please reload the page.",
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
  errors: {
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
  },
  // Code review finding: `{field}` is a product-owned label of arbitrary grammatical number (e.g.
  // "Progress notes"), so no message here may make it the subject of a verb that agrees with number
  // ("is"/"are", French "est"/"sont", German "ist"/"sind", ...) -- every message is a label-colon-
  // fragment instead, which needs no agreement in any of the seven locales.
  validation: {
    required: "{field}: required.",
    outerWhitespace: "{field}: no leading or trailing whitespace.",
    maxLength: "{field}: {maxLength, plural, one {# character} other {# characters}} maximum.",
  },
};
