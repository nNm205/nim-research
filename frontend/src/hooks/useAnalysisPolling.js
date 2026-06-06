import { useEffect, useRef, useState, useCallback } from "react";
import { analysisService } from "../services/analysisService";

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 100; // ~5 minutes max

/**
 * Load an analysis by id and keep polling while its status is pending/running.
 * Returns { analysis, loading, error }.
 *
 * State updates happen inside async callbacks (the load function and the poll
 * timeout), never directly in an effect body, so this plays nicely with
 * `react-hooks/set-state-in-effect`.
 */
export function useAnalysisPolling(analysisId) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const timerRef = useRef(null);
  const attemptsRef = useRef(0);
  const aliveRef = useRef(true);
  // We hold the schedule function in a ref so it can recurse without
  // tripping use-before-declaration on the actual symbol. This also lets
  // us re-use the latest fetch implementation if the analysis id changes.
  const scheduleRef = useRef(null);

  const fetchOnce = useCallback(
    async (silent) => {
      try {
        const data = await analysisService.getAnalysis(analysisId);
        if (!aliveRef.current) return data;
        setAnalysis(data);
        setError("");
        return data;
      } catch (err) {
        console.error(err);
        if (aliveRef.current && !silent) {
          setError("Không thể tải kết quả phân tích");
        }
        return null;
      } finally {
        if (aliveRef.current && !silent) setLoading(false);
      }
    },
    [analysisId]
  );

  const schedule = useCallback(
    (current) => {
      clearTimeout(timerRef.current);
      if (!current) return;
      const isInFlight =
        current.status === "pending" || current.status === "running";
      if (!isInFlight) return;
      if (attemptsRef.current >= POLL_MAX_ATTEMPTS) return;

      timerRef.current = setTimeout(async () => {
        attemptsRef.current += 1;
        const next = await fetchOnce(true);
        if (next && scheduleRef.current) scheduleRef.current(next);
      }, POLL_INTERVAL_MS);
    },
    [fetchOnce]
  );

  // Keep the ref in sync so the timeout callback can call the latest schedule
  useEffect(() => {
    scheduleRef.current = schedule;
  }, [schedule]);

  // Initial load + cleanup on unmount or id change
  useEffect(() => {
    aliveRef.current = true;
    attemptsRef.current = 0;

    (async () => {
      const initial = await fetchOnce(false);
      schedule(initial);
    })();

    return () => {
      aliveRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, [analysisId, fetchOnce, schedule]);

  return { analysis, loading, error };
}
