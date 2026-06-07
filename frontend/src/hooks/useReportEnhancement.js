import { useCallback, useEffect, useRef, useState } from "react";
import { synthesisService } from "../services/synthesisService";
import { qaService } from "../services/qaService";

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 200; // ~10 minutes of polling

/**
 * Track Synthesis + QA status + progress for a single Report.
 *
 * Works the same way as ``useAnalysisPolling`` — polls only while a
 * pipeline is actively pending/running, never spins forever, and exposes
 * the latest status payloads to the consumer.
 *
 * Callers get:
 *   - ``synthesis``  — the latest /synthesis/status payload
 *   - ``qa``         — the latest /qa/status payload (with progress + report stub)
 *   - ``loading``    — true on initial fetch only
 *   - ``refresh()``  — force-fetch both right now (used after dispatch)
 */
export function useReportEnhancement(reportId) {
  const [synthesis, setSynthesis] = useState(null);
  const [qa, setQa] = useState(null);
  const [loading, setLoading] = useState(true);

  const aliveRef = useRef(true);
  const timerRef = useRef(null);
  const attemptsRef = useRef(0);
  const scheduleRef = useRef(null);

  const fetchOnce = useCallback(
    async (silent) => {
      if (!reportId) return null;
      try {
        const [syn, q] = await Promise.all([
          synthesisService.getStatus(reportId),
          qaService.getStatus(reportId),
        ]);
        if (!aliveRef.current) return { syn, q };
        setSynthesis(syn);
        setQa(q);
        return { syn, q };
      } catch (err) {
        // Silent on poll ticks — backend may briefly 404 right after
        // delete; we'll just retry on the next interval.
        if (!silent) console.error(err);
        return null;
      } finally {
        if (aliveRef.current && !silent) setLoading(false);
      }
    },
    [reportId]
  );

  const isInFlight = (statusValue) =>
    statusValue === "pending" || statusValue === "running";

  const schedule = useCallback(
    (latest) => {
      clearTimeout(timerRef.current);
      if (!latest) return;
      const synBusy = isInFlight(latest.syn?.synthesis_status);
      const qaBusy = isInFlight(latest.q?.qa_status);
      if (!synBusy && !qaBusy) return;
      if (attemptsRef.current >= POLL_MAX_ATTEMPTS) return;

      timerRef.current = setTimeout(async () => {
        attemptsRef.current += 1;
        const next = await fetchOnce(true);
        if (next && scheduleRef.current) scheduleRef.current(next);
      }, POLL_INTERVAL_MS);
    },
    [fetchOnce]
  );

  useEffect(() => {
    scheduleRef.current = schedule;
  }, [schedule]);

  // Initial fetch + cleanup
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
  }, [reportId, fetchOnce, schedule]);

  // Force re-fetch immediately and re-schedule polling. Caller invokes
  // this after dispatching a pipeline so we don't have to wait for the
  // next 3 s tick to see "pending" or "running".
  const refresh = useCallback(async () => {
    attemptsRef.current = 0;
    const next = await fetchOnce(true);
    if (next) schedule(next);
    return next;
  }, [fetchOnce, schedule]);

  return { synthesis, qa, loading, refresh };
}
