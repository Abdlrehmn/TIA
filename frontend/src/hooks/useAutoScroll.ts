import { useEffect, useRef } from "react";

/** Keep a scrollable element pinned to the bottom whenever `dep` changes. */
export function useAutoScroll<T extends HTMLElement>(dep: number) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [dep]);

  return ref;
}
