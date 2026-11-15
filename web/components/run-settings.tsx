"use client";

import { useEffect, useState } from "react";
import { type Run, request } from "../lib/types";

/** Choose a saved run, or start a bounded run whose animal photos span a period. */
export default function RunSettings({
  runs,
  runId,
  createdAt,
  onSwitch,
  onStarted,
  onError,
  canStartRuns = true,
}: {
  canStartRuns?: boolean;
  runs: Run[];
  runId: string;
  createdAt?: string;
  onSwitch: (id: string) => void;
  onStarted: (id: string) => void;
  onError: (message: string) => void;
}) {
  const [starting, setStarting] = useState(false);
  const [limit, setLimit] = useState(12);
  const [before, setBefore] = useState("2024-12-31");
  const [after, setAfter] = useState("2010-01-01");
  // The API rejects periods ending after its local date; set on the client, not at build.
  const [today, setToday] = useState("");
  useEffect(() => setToday(new Date().toLocaleDateString("en-CA")), []);

  async function start() {
    setStarting(true);
    try {
      const result = await request<{ id: string }>("runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit_per_region: limit,
          controls_per_species: 1,
          before,
          after,
          sampling: "stratified",
        }),
      });
      onStarted(result.id);
    } catch (failure) {
      onError(String(failure));
    } finally {
      setStarting(false);
    }
  }

  return (
    <details className="run-settings">
      <summary>
        Run & collection settings{" "}
        <span>{createdAt?.slice(0, 10) ?? "No run yet"} · historical photo study</span>
      </summary>
      <div className="settings-grid">
        <label>
          Saved run
          <select value={runId} onChange={(event) => onSwitch(event.target.value)}>
            {runs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} · {item.status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Animal photos per region
          <input
            type="number"
            min={1}
            max={50}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </label>
        <label>
          Photographed on or after
          <input
            type="date"
            min="2008-01-01"
            value={after}
            onChange={(event) => setAfter(event.target.value)}
          />
        </label>
        <label>
          Photographed on or before
          <input
            type="date"
            max={today || undefined}
            value={before}
            onChange={(event) => setBefore(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="primary"
          disabled={
            !canStartRuns ||
            starting ||
            !Number.isInteger(limit) ||
            limit < 1 ||
            limit > 50 ||
            !before ||
            !after ||
            after < "2008-01-01" ||
            after > before ||
            !today ||
            before > today
          }
          onClick={start}
        >
          {starting ? "Starting…" : "Start bounded run ↗"}
        </button>
      </div>
      {!canStartRuns && (
        <p role="status">
          Collection processing is unavailable right now. Existing evidence can be reviewed.
        </p>
      )}
      <p>
        Animal photos are spread across every season in the period, at most one per observer per
        day. Also requests one reference photo for each of three target species in each region.
        Queries use current council boundaries and eligible CC0, CC BY or CC BY-NC photos and
        metadata.
      </p>
    </details>
  );
}
