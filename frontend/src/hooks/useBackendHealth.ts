import { useEffect, useState } from "react";
import { ApiError, getBackendHealth } from "../lib/api";

export type BackendConnectionState = "checking" | "online" | "offline";

interface BackendHealth {
  state: BackendConnectionState;
  error: ApiError | null;
}

/** How often backend availability is re-checked while a component is mounted. */
const HEALTH_CHECK_INTERVAL_MS = 3_000;

/**
 * Check backend availability immediately on mount, then every 3 seconds.
 *
 * - Only one request is in flight at a time; a tick that fires while a check is
 *   still running is skipped.
 * - Each request uses the API helper's own 5-second timeout.
 * - State stays "checking" until the first result, then follows the latest
 *   result ("online" / "offline") without flickering back to "checking".
 * - On unmount the interval is cleared and any outstanding request is aborted.
 */
export function useBackendHealth(): BackendHealth {
  const [health, setHealth] = useState<BackendHealth>({ state: "checking", error: null });

  useEffect(() => {
    let activeRequest: AbortController | null = null;

    const checkHealth = async () => {
      if (activeRequest) return;

      const request = new AbortController();
      activeRequest = request;

      try {
        await getBackendHealth({ signal: request.signal });
        if (request.signal.aborted) return;

        // Keep the same state object when nothing changed so the polling does
        // not re-render the whole chat screen every 3 seconds.
        setHealth((current) =>
          current.state === "online" ? current : { state: "online", error: null },
        );
      } catch (error: unknown) {
        if (request.signal.aborted) return;

        const apiError =
          error instanceof ApiError
            ? error
            : new ApiError("network", "Could not connect to the TIA backend.");

        setHealth((current) =>
          current.state === "offline" &&
          current.error?.code === apiError.code &&
          current.error?.status === apiError.status
            ? current
            : { state: "offline", error: apiError },
        );
      } finally {
        if (activeRequest === request) activeRequest = null;
      }
    };

    void checkHealth();
    const intervalId = window.setInterval(() => void checkHealth(), HEALTH_CHECK_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
      activeRequest?.abort();
    };
  }, []);

  return health;
}
