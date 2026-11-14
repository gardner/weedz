import { useCallback, useEffect, useRef } from "react";

/** Input-free time after which a photo is treated as left open, not reviewed. */
export const IDLE_LIMIT_MS = 10 * 60_000;
const TICK_MS = 1_000;
const ACTIVITY = ["pointerdown", "pointermove", "keydown", "wheel", "scroll"] as const;

/** The time measured on one photo when a decision was sent. */
export type EffortSnapshot = { seconds: number; measurement: number };

/**
 * Seconds spent actively reviewing the current photo: counted only while the tab is
 * visible and within ten minutes of the last input. Take a `snapshot()` when sending a
 * decision and `clear()` it only once the save succeeds, so a failed save keeps the
 * measured time and a slow save never clears time spent on the next photo.
 */
export function useReviewTimer(photoKey: string) {
  const elapsed = useRef(0);
  const measurement = useRef(0);
  const lastActivity = useRef(Date.now());

  useEffect(() => {
    // A new photo starts a fresh measurement.
    void photoKey;
    measurement.current++;
    elapsed.current = 0;
    lastActivity.current = Date.now();
  }, [photoKey]);

  useEffect(() => {
    const touch = () => {
      lastActivity.current = Date.now();
    };
    const tick = setInterval(() => {
      const active = Date.now() - lastActivity.current <= IDLE_LIMIT_MS;
      if (document.visibilityState === "visible" && active) elapsed.current += TICK_MS;
    }, TICK_MS);
    for (const event of ACTIVITY) window.addEventListener(event, touch, { passive: true });
    document.addEventListener("visibilitychange", touch);
    return () => {
      clearInterval(tick);
      for (const event of ACTIVITY) window.removeEventListener(event, touch);
      document.removeEventListener("visibilitychange", touch);
    };
  }, []);

  const snapshot = useCallback(
    (): EffortSnapshot => ({ seconds: elapsed.current / 1000, measurement: measurement.current }),
    [],
  );
  const clear = useCallback((saved: EffortSnapshot) => {
    // Time counted after the snapshot, or on another photo, belongs to the next decision.
    if (saved.measurement === measurement.current) elapsed.current -= saved.seconds * 1000;
  }, []);
  return { snapshot, clear };
}
