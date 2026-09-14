export type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

/** Generic safe error/quota-exhausted display: a message plus an optional retry action. Never
 * passed raw backend/exception text -- callers own picking a user-safe `message`. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
