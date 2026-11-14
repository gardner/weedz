"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { imageUrl, names, type Photo, type Run, request, type Status } from "../lib/types";
import Evidence from "./evidence";

export default function ReviewDesk() {
  const requestGeneration = useRef(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [activeId, setActiveId] = useState("");
  const [cohort, setCohort] = useState("incidental");
  const [region, setRegion] = useState("all");
  const [review, setReview] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [limit, setLimit] = useState(12);
  const [before, setBefore] = useState("2024-12-31");
  const [after, setAfter] = useState("2010-01-01");
  const run = runs.find((item) => item.id === runId);

  const refresh = useCallback(async () => {
    const generation = ++requestGeneration.current;
    try {
      const list = await request<Run[]>("runs");
      if (generation !== requestGeneration.current) return;
      setRuns(list);
      const selected = runId || list[0]?.id;
      if (selected) {
        if (!runId) setRunId(selected);
        const result = await request<{ run: Run; photos: Photo[] }>(`runs/${selected}`);
        if (generation !== requestGeneration.current) return;
        setPhotos(result.photos);
      }
      setError("");
    } catch (failure) {
      if (generation !== requestGeneration.current) return;
      setError(failure instanceof Error ? failure.message : "Unable to load the run");
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => {
      requestGeneration.current++;
      clearInterval(timer);
    };
  }, [refresh]);

  const filtered = photos
    .filter(
      (photo) =>
        photo.cohort === cohort &&
        (region === "all" || photo.region === region) &&
        (review === "all" || photo.review_status === review),
    )
    .sort((a, b) => (b.scores.margin ?? -2) - (a.scores.margin ?? -2));
  const active = filtered.find((photo) => photo.id === activeId) ?? filtered[0];
  const incidental = photos.filter((photo) => photo.cohort === "incidental");
  const reviewed = incidental.filter((photo) => photo.review_status !== "unreviewed").length;

  async function save(status: Status, note: string) {
    if (!active) return;
    setSaving(true);
    try {
      await request(`runs/${runId}/photos/${active.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, note }),
      });
      setNotice("Review saved locally.");
      await refresh();
    } catch (failure) {
      setError(String(failure));
    } finally {
      setSaving(false);
    }
  }

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
      setPhotos([]);
      setActiveId("");
      setRunId(result.id);
      setNotice("Regional run queued. Progress updates automatically.");
    } catch (failure) {
      setError(String(failure));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-symbol">w</span>weedz<span className="brand-dot">.</span>
        </a>
        <p className="sidebar-tagline">
          Small clues.
          <br />
          Healthier landscapes.
        </p>
        <div className="nav-label">WORKSPACE</div>
        <div className="nav-active">
          <span aria-hidden="true">◉</span> Field review{" "}
          <span className="nav-count">{incidental.length}</span>
        </div>
        <a
          className="nav-link"
          href={process.env.NEXT_PUBLIC_TEMPORAL_UI_URL ?? "http://127.0.0.1:8234"}
          target="_blank"
          rel="noreferrer"
        >
          ↗ Workflow history
        </a>
        <div className="pilot-card">
          <span className="eyebrow">REGIONAL PILOT</span>
          <strong>Nelson / Tasman</strong>
          <span>New Zealand · Aotearoa</span>
          <div className="pilot-line" />
          <p>Finding plants in photos taken for something else.</p>
        </div>
        <div className="sidebar-footer">
          <span className="live-dot" /> Open source. Public good.
          <small>Non-commercial conservation research</small>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            DISCOVERY / <b>FIELD REVIEW</b>
          </span>
          <span className="topbar-tag">NELSON / TASMAN</span>
        </header>
        <div className="page-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">LOOK CLOSER</span>
              <h1>Evidence in the background.</h1>
              <p>Review possible invasive plants. Keep every finding tied to its source.</p>
            </div>
            {runId && (
              <a className="button export-button" href={`/api/runs/${runId}/export`}>
                Export evidence ↓
              </a>
            )}
          </div>
          {error && (
            <div role="alert" className="error-banner">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          <div className="stats-grid">
            <div>
              <span>Incidental photos</span>
              <strong>{incidental.length.toString().padStart(2, "0")}</strong>
              <small>Animal subjects · background unlabelled</small>
            </div>
            <div>
              <span>Reviewed</span>
              <strong>
                {reviewed.toString().padStart(2, "0")}
                <em> / {incidental.length}</em>
              </strong>
              <small>Human decisions, with an audit trail</small>
            </div>
            <div>
              <span>Reference photos</span>
              <strong>
                {photos
                  .filter((photo) => photo.cohort === "reference")
                  .length.toString()
                  .padStart(2, "0")}
              </strong>
              <small>Separate from incidental discoveries</small>
            </div>
            <div className="run-stat">
              <span>Workflow status</span>
              <strong className="status-name">{run?.status ?? "Ready to begin"}</strong>
              <small>{run?.detail || "Python + Temporal · local CPU screening"}</small>
            </div>
          </div>
          <details className="run-settings">
            <summary>
              Run & collection settings{" "}
              <span>{run?.created_at.slice(0, 10) ?? "No run yet"} · historical photo study</span>
            </summary>
            <div className="settings-grid">
              <label>
                Saved run
                <select
                  value={runId}
                  onChange={(event) => {
                    setPhotos([]);
                    setRunId(event.target.value);
                    setActiveId("");
                  }}
                >
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
                  value={after}
                  onChange={(event) => setAfter(event.target.value)}
                />
              </label>
              <label>
                Photographed on or before
                <input
                  type="date"
                  value={before}
                  onChange={(event) => setBefore(event.target.value)}
                />
              </label>
              <button
                type="button"
                className="primary"
                disabled={
                  starting ||
                  !Number.isInteger(limit) ||
                  limit < 1 ||
                  limit > 50 ||
                  !before ||
                  !after ||
                  after > before
                }
                onClick={start}
              >
                {starting ? "Starting…" : "Start bounded run ↗"}
              </button>
            </div>
            <p>
              Animal photos are spread across every season in the period, at most one per observer
              per day. Also requests one reference photo for each of three target species in each
              region. Queries use current council boundaries and eligible CC0, CC BY or CC BY-NC
              photos and metadata.
            </p>
          </details>
          <div className="screening-note">
            <span className="note-icon" aria-hidden="true">
              i
            </span>
            <p>
              <strong>Screening, awaiting expert review.</strong> BioCLIP ranks full images and
              overlapping windows. Scores are similarities, not probabilities. Location novelty and
              weed boundaries have not been established.
            </p>
          </div>
          <div className="workspace">
            <section className="queue" aria-label="Photo review queue">
              <div className="queue-heading">
                <h2>
                  Review queue <span>{filtered.length}</span>
                </h2>
                <p>Highest relative similarity first</p>
              </div>
              <div className="cohort-tabs">
                <button
                  type="button"
                  aria-pressed={cohort === "incidental"}
                  onClick={() => setCohort("incidental")}
                >
                  Incidental photos
                </button>
                <button
                  type="button"
                  aria-pressed={cohort === "reference"}
                  onClick={() => setCohort("reference")}
                >
                  References
                </button>
              </div>
              <div className="queue-filters">
                <select
                  aria-label="Filter region"
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                >
                  <option value="all">Both regions</option>
                  <option>Nelson</option>
                  <option>Tasman</option>
                </select>
                <select
                  aria-label="Filter review status"
                  value={review}
                  onChange={(event) => setReview(event.target.value)}
                >
                  <option value="all">All decisions</option>
                  <option value="unreviewed">Needs review</option>
                  <option value="confirmed">Species visible</option>
                  <option value="rejected">Rejected</option>
                  <option value="uncertain">Uncertain</option>
                </select>
              </div>
              <div className="photo-list">
                {filtered.map((photo, index) => (
                  <button
                    type="button"
                    key={photo.id}
                    className={`photo-row ${active?.id === photo.id ? "selected" : ""}`}
                    onClick={() => {
                      setActiveId(photo.id);
                      setNotice("");
                    }}
                    aria-pressed={active?.id === photo.id}
                  >
                    <Image
                      src={imageUrl(runId, photo.id)}
                      alt={photo.original_common_name || photo.original_taxon}
                      loading="lazy"
                      width={68}
                      height={74}
                      unoptimized
                    />
                    <span className="photo-row-body">
                      <span className="row-index">
                        {String(index + 1).padStart(2, "0")} / {photo.region}
                      </span>
                      <strong>
                        {names[photo.scores.best_species ?? ""] ?? "Awaiting screening"}
                      </strong>
                      <span>{photo.original_common_name || photo.original_taxon}</span>
                      <small>
                        {photo.observed_on ?? "Date unknown"} ·{" "}
                        {photo.review_status === "unreviewed"
                          ? "Needs review"
                          : photo.review_status}
                      </small>
                    </span>
                  </button>
                ))}
                {!filtered.length && (
                  <div className="empty-state">
                    {loading
                      ? "Loading local evidence…"
                      : run?.status === "acquiring"
                        ? "Collecting eligible source photos…"
                        : "No photos match this view."}
                  </div>
                )}
              </div>
            </section>
            {active ? (
              <Evidence
                key={`${runId}:${active.id}`}
                photo={active}
                runId={runId}
                onSave={save}
                saving={saving}
              />
            ) : (
              <div className="evidence empty-evidence">
                <span className="eyebrow">THE NEXT CLUE</span>
                <h2>A closer look starts here.</h2>
                <p>
                  {runId
                    ? "Photos will appear as the regional workflow collects and screens them."
                    : "Open Run & collection settings to start the Nelson / Tasman pilot."}
                </p>
              </div>
            )}
            <aside className="field-notes">
              <span className="eyebrow">FIELD NOTES</span>
              <h3>Read the whole scene.</h3>
              <p>Original labels describe the observed animal, not every plant in the photo.</p>
              <div className="notes-rule" />
              <h4>Provisional watchlist</h4>
              {Object.entries(names).map(([scientific, common]) => (
                <div className="watch-species" key={scientific}>
                  <strong>{common}</strong>
                  <em>{scientific}</em>
                </div>
              ))}
              <div className="notes-rule" />
              <h4>Check the lookalikes</h4>
              <p>
                Native clematis and toetoe can resemble targets. A model ranking alone cannot
                resolve species.
              </p>
              {active?.scores.species && (
                <>
                  <h4>Similarity comparison</h4>
                  {active.scores.species.map((species) => (
                    <div className="score-row" key={species.name}>
                      <span>{names[species.name]}</span>
                      <b>{species.similarity.toFixed(3)}</b>
                    </div>
                  ))}
                  <small>
                    Raw cosine similarity. Ranking uses the margin against comparison labels.
                  </small>
                </>
              )}
              <div className="notes-rule" />
              <p className="location-note">
                A photo location is an observation location. It may be obscured, approximate or
                distant from the plant.
              </p>
            </aside>
          </div>
          <footer className="page-footer">
            <span>WEEDZ · COMMUNITY CONSERVATION RESEARCH</span>
            <span>Source → screening → human review → evidence</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
