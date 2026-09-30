"use client";

import type { CSSProperties } from "react";
import styles from "./ModeSwitch.module.css";

/** The radio-group mode selector shared by multi-mode products (each mode is its own
 * `ProductDefinition`). `disabled` blocks a switch while a run is active: switching remounts
 * `ProductRunPage` and would abandon an accepted run. */
export function ModeSwitch<Id extends string>({
  legend,
  name,
  options,
  value,
  disabled,
  onChange,
}: {
  legend: string;
  name: string;
  options: ReadonlyArray<{ id: Id; label: string }>;
  value: Id;
  disabled: boolean;
  onChange: (id: Id) => void;
}) {
  return (
    <fieldset className={styles.modeGroup}>
      <legend className={styles.legend}>{legend}</legend>
      <div className={styles.modeOptions} style={{ "--mode-count": options.length } as CSSProperties}>
        {options.map(({ id, label }) => (
          <label key={id} className={styles.modeOption}>
            <input
              className={styles.radio}
              type="radio"
              name={name}
              value={id}
              checked={id === value}
              disabled={disabled}
              // The `disabled` attribute is the real guard; this is a second, independent one.
              onChange={() => !disabled && onChange(id)}
            />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
