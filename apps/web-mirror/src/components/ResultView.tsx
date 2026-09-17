"use client";

import { Card, CopyButton } from "@anytoolai/shared-ui";
import { GeneratedTextRenderer } from "@anytoolai/web-result-kit";

export type ResultViewProps = {
  text: string;
  /** Called once the clipboard write itself succeeds. Which (if any) next action to fire after a
   * copy is product-specific, so it stays out of this shared component. */
  onCopied?: () => void;
};

/** Canonical text result plus a copy-to-clipboard button. */
export function ResultView({ text, onCopied }: ResultViewProps) {
  return (
    <Card>
      <GeneratedTextRenderer text={text} />
      <CopyButton text={text} onCopied={onCopied} />
    </Card>
  );
}
