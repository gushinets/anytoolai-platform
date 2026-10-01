import { useEffect, useRef, type MutableRefObject } from "react";

/** A ref that always holds the latest value, refreshed after every render: for a callback or value that an
 * async continuation or a once-run effect must read current, without making it a dependency. */
export function useLatest<T>(value: T): MutableRefObject<T> {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref;
}
