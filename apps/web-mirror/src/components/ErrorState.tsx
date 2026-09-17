import { Button, Card, Toast } from "@anytoolai/shared-ui";

export type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

/** Generic safe error/quota-exhausted display: a message plus an optional retry action. Never
 * passed raw backend/exception text -- callers own picking a user-safe `message`. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Card>
      <Toast variant="error">{message}</Toast>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </Card>
  );
}
