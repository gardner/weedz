import { useCallback, useEffect, useRef } from "react";

/** Input-free time after which a photo is treated as left open, not reviewed. */
export const IDLE_LIMIT_MS = 10 * 60_000;
const TICK_MS = 1_000;
const ACTIVITY = ["pointerdown", "pointermove", "keydown", "wheel", "scroll"] as const;

/**
 * Seconds spent actively reviewing the current photo: counted only while the tab is
 * visible and within ten minutes of the last input. Read it with `seconds()` and call
 * `reset()` only once a decision is saved, so a failed save keeps the measured time.
 */
export function useReviewTimer(photoKey: string) {
  const elapsed = useRef(0);
  const lastActivity = useRef(Date.now());

  useEffect(() => {
    // A new photo starts a fresh measurement.
    void photoKey;
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

  const seconds = useCallback(() => elapsed.current / 1000, []);
  const reset = useCallback(() => {
    elapsed.current = 0;
  }, []);
  return { seconds, reset };
}
