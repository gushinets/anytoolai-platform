// English is the semantic source of truth for every host key; the other locale files are typed
// `Shape<typeof en>`. Apostrophes are safe in ICU unless directly followed by `{` -- translators
// use the typographic ’ everywhere so a placeholder is never swallowed by ICU quoting.
export const en = {
  language: { label: "Language" },
  loading: "Loading {product}…",
  unavailable: "{product} is unavailable right now. Please reload the page.",
  quotaExhausted: "You've used all your {product} runs for now.",
  resultFetchFailed: "Your result is ready, but we couldn't load it. Please try again.",
  starting: "Starting…",
  generating: "Generating…",
  identityUnavailable: "We couldn't verify your identity. Please reload the page and try again.",
  retry: "Try again",
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
  validation: {
    required: "{field} is required.",
    outerWhitespace: "{field} must not start or end with whitespace.",
    maxLength: "{field} must be {maxLength, plural, one {# character} other {# characters}} or fewer.",
  },
  // Visible labels for the `tone` wire values (`neutral|warm|firm`), shared by every product whose
  // input schema declares that enum. The values sent to the backend are never translated.
  tone: { neutral: "neutral", warm: "warm", firm: "firm" },
};
