import type { CSSProperties } from "react";
import styles from "./Spinner.module.css";

export type SpinnerProps = {
  size?: number;
};

/** Purely decorative -- callers pair it with their own `role="status"` text (see
 * `ProductRunPage`), so this never announces its own accessible name. */
export function Spinner({ size = 16 }: SpinnerProps) {
  return (
    <span
      className={styles.spinner}
      aria-hidden="true"
      style={{ "--spinner-size": `${size}px` } as CSSProperties}
    />
  );
}
