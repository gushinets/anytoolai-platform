import { useEffect, useState } from "react";
import { useHostT } from "../../i18n";
import styles from "./ProductRunPage.module.css";

// ANY-842 measured 4.5–42 s across products, with discomfort from about 20 s without a duration cue.
export const RUN_PROGRESS_SLOW_AFTER_S = 30;
export const RUN_PROGRESS_LONG_AFTER_S = 60;
const TICK_MS = 1_000;

type Props = { phase: "submitting" | "running"; startedAtMs: number; statusText: string; className?: string };

export function RunProgress({ phase, startedAtMs, statusText, className }: Props) {
  const th = useHostT();
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    setNowMs(Date.now());
    const id = window.setInterval(() => setNowMs(Date.now()), TICK_MS);
    return () => window.clearInterval(id);
  }, [startedAtMs]);
  const elapsedS = Math.max(0, Math.floor((nowMs - startedAtMs) / 1_000));
  const stage = elapsedS >= RUN_PROGRESS_LONG_AFTER_S ? "long"
    : elapsedS >= RUN_PROGRESS_SLOW_AFTER_S ? "slow" : "normal";
  return (
    <div className={className} data-testid="run-progress" data-stage={stage}>
      <p role="status">
        {statusText} <span>{th(`runProgress.${phase === "submitting" ? "confirmingStart" : stage}`)}</span>
      </p>
      <p className={styles.runElapsed} role="timer" aria-live="off">
        {th("runProgress.elapsed", { time: formatElapsed(elapsedS) })}
      </p>
    </div>
  );
}

export function formatElapsed(totalS: number): string {
  return `${Math.floor(totalS / 60)}:${String(totalS % 60).padStart(2, "0")}`;
}
