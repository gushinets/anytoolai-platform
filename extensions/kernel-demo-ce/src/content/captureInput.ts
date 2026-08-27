const MAX_CAPTURED_CHARS = 4000;

/** Captures the current page's visible text as the scenario's `source_text` input. */
export function captureInput(): { text: string } {
  const text = document.body?.innerText?.trim() ?? "";
  return { text: text.slice(0, MAX_CAPTURED_CHARS) };
}
