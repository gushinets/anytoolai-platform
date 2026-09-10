export type GeneratedTextRendererProps = {
  text: string;
};

/**
 * Renders a canonical plain-text workflow result verbatim -- no markdown/HTML interpretation, no
 * truncation. `white-space: pre-wrap` preserves the author's line breaks without letting long
 * lines force horizontal scroll.
 */
export function GeneratedTextRenderer({ text }: GeneratedTextRendererProps) {
  return <p style={{ whiteSpace: "pre-wrap" }}>{text}</p>;
}
