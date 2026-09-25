"use client";

import { Button, Card, Toast } from "@anytoolai/shared-ui";
import { useHostT } from "../i18n";
import styles from "./cardStack.module.css";

export type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

/** Generic safe error/quota-exhausted display: a message plus an optional retry action. Never
 * passed raw backend/exception text -- callers own picking a user-safe `message`. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  const t = useHostT();
  return (
    <Card className={styles.stack}>
      <Toast variant="error">{message}</Toast>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          {t("retry")}
        </Button>
      ) : null}
    </Card>
  );
}
