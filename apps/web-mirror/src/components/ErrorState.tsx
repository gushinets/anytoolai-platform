"use client";

import { Button, Card, Toast } from "@anytoolai/shared-ui";
import { useHostT } from "../i18n";
import styles from "./cardStack.module.css";

export type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
  /** Render inside an existing Card without adding a second card surface. */
  embedded?: boolean;
};

/** Generic safe error/quota-exhausted display: a message plus an optional retry action. Never
 * passed raw backend/exception text -- callers own picking a user-safe `message`. */
export function ErrorState({ message, onRetry, embedded = false }: ErrorStateProps) {
  const t = useHostT();
  const Container = embedded ? "div" : Card;
  return (
    <Container className={styles.stack}>
      <Toast variant="error">{message}</Toast>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          {t("retry")}
        </Button>
      ) : null}
    </Container>
  );
}
