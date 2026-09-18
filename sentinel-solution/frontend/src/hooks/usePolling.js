import { useCallback, useEffect } from "react";

// Shared setInterval+cleanup for the top-level catalogue/health/alert polls —
// App.jsx previously repeated this same fetch/setState/try-catch/interval
// pattern four times with only the fetcher and interval differing.
export function usePolling(fetchFn, setValue, intervalMs, deps = [], onError) {
  const run = useCallback(async () => {
    try {
      setValue(await fetchFn());
    } catch (err) {
      // Transient failure on a polled endpoint; the next tick retries.
      // Callers with a dedicated error UI (e.g. AlertsView) handle their
      // own fetch separately from this top-level poll. `onError` lets a
      // caller replace the displayed value on failure (e.g. health must
      // drop to "unknown", not silently keep showing the last-known-good
      // state, per CLAUDE.md's truthful-degraded-state rule (section 24.11).
      onError?.(err);
    }
    // oxlint-disable-next-line react/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    const id = setInterval(run, intervalMs);
    return () => clearInterval(id);
  }, [run, intervalMs]);

  return run;
}

export function useCameraPolling(api, setCameras, intervalMs, deps) {
  return usePolling(() => api.listCameras(), setCameras, intervalMs, deps);
}

export function useAlertPolling(api, setAlerts, intervalMs, deps) {
  return usePolling(() => api.listAlerts(), setAlerts, intervalMs, deps);
}

export function useHealthPolling(api, setHealth, intervalMs) {
  return usePolling(() => api.health(), setHealth, intervalMs, [], () => setHealth(null));
}
