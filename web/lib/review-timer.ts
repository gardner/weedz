import { useCallback, useEffect, useRef } from "react";

/** Input-free time after which a photo is treated as left open, not reviewed. */
export const IDLE_LIMIT_MS = 10 * 60_000;
const TICK_MS = 1_000;
const ACTIVITY = ["pointerdown", "pointermove", "keydown", "wheel", "scroll"] as const;

/** The time measured on one photo when a decision was sent. */
export type EffortSnapshot = { photoKey: string; seconds: number };

/**
 * Seconds spent actively reviewing each photo: counted only while the tab is visible
 * and within ten minutes of the last input. Time is kept per photo, so looking at a
 * reference or changing a filter never discards it. Take a `snapshot()` when sending a
 * decision and `clear()` it only once the save succeeds, so a failed save keeps the
 * measured time and a slow save never clears time spent on another photo.
 */
export function useReviewTimer(photoKey: string) {
  const elapsed = useRef(new Map<string, number>());
  const current = useRef(photoKey);
  const lastActivity = useRef(Date.now());

  useEffect(() => {
    current.current = photoKey;
    lastActivity.current = Date.now();
  }, [photoKey]);

  useEffect(() => {
    const touch = () => {
      lastActivity.current = Date.now();
    };
    const tick = setInterval(() => {
      const active = Date.now() - lastActivity.current <= IDLE_LIMIT_MS;
      if (document.visibilityState !== "visible" || !active) return;
      const key = current.current;
      elapsed.current.set(key, (elapsed.current.get(key) ?? 0) + TICK_MS);
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
    (): EffortSnapshot => ({ photoKey, seconds: (elapsed.current.get(photoKey) ?? 0) / 1000 }),
    [photoKey],
  );
  const clear = useCallback((saved: EffortSnapshot) => {
    // Time counted on this photo after the snapshot belongs to its next decision.
    const left = (elapsed.current.get(saved.photoKey) ?? 0) - saved.seconds * 1000;
    if (left > 0) elapsed.current.set(saved.photoKey, left);
    else elapsed.current.delete(saved.photoKey);
  }, []);
  return { snapshot, clear };
}
