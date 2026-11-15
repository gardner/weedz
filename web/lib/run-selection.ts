import type { Run } from "./types";

/** Prefer an operator-selected completed collection; otherwise use the newest completed run. */
export function initialRun(runs: Run[], preferred?: string): string | undefined {
  return (
    runs.find((run) => run.id === preferred && run.status === "completed")?.id ??
    runs.find((run) => run.status === "completed")?.id ??
    runs[0]?.id
  );
}
