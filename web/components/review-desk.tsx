"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import type { NewFinding } from "../lib/findings";
import type { NewJudgement } from "../lib/judgements";
import { auditedBy, heldForAudit, queuePhotos, VIEWS, type View } from "../lib/queue";
import { useReviewTimer } from "../lib/review-timer";
import {
  type AuditSummary,
  effortNote,
  imageUrl,
  names,
  type Photo,
  type References,
  type ReviewEffort,
  type Run,
  type RunDetail,
  request,
  type Status,
  siteVisitNote,
} from "../lib/types";
import AuditPanel from "./audit-panel";
import Evidence from "./evidence";
import FieldNotes from "./field-notes";
import RunSettings from "./run-settings";

const REVIEWER_KEY = "weedz-reviewer";
type Payloads = {
  review: { status: Status; note: string };
  audit: { finding: string; note: string };
  findings: NewFinding;
  judgements: NewJudgement;
};
const SAVED: Record<keyof Payloads, string> = {
  review: "Review saved locally.",
  audit: "Audit saved locally.",
  findings: "Finding saved locally.",
  judgements: "Judgement saved locally.",
};

export default function ReviewDesk() {
  const requestGeneration = useRef(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [references, setReferences] = useState<References>(null);
  const [effortSummary, setEffortSummary] = useState<ReviewEffort>();
  const [auditSummary, setAuditSummary] = useState<AuditSummary>();
  // Each view remembers its own open photo, so one opened in a view never carries into
  // another (an audit photo must not open in the ranked queue) yet a glance at the
  // references returns to the same incidental photo.
  const [activeIds, setActiveIds] = useState<Partial<Record<View, string>>>({});
  const [cohort, setCohort] = useState<View>("incidental");
  const [region, setRegion] = useState("all");
  const [review, setReview] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reviewer, setReviewer] = useState("");
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
        const result = await request<RunDetail>(`runs/${selected}`);
        if (generation !== requestGeneration.current) return;
        setPhotos(result.photos);
        setEffortSummary(result.review_effort);
        setAuditSummary(result.audit);
        setReferences(result.references ?? null);
      }
      setError("");
    } catch (failure) {
      if (generation !== requestGeneration.current) return;
      setError(failure instanceof Error ? failure.message : "Unable to load the run");
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [runId]);
  // A save that finishes after a run change must reload the run now selected.
  const latestRefresh = useRef(refresh);
  latestRefresh.current = refresh;

  useEffect(() => {
    try {
      setReviewer(localStorage.getItem(REVIEWER_KEY) ?? "");
    } catch {
      // Storage can be unavailable; the name is then entered each session.
    }
  }, []);

  function changeReviewer(name: string) {
    setReviewer(name);
    try {
      localStorage.setItem(REVIEWER_KEY, name.trim());
    } catch {
      // Not remembered, but still sent with this session's decisions.
    }
  }

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => {
      requestGeneration.current++;
      clearInterval(timer);
    };
  }, [refresh]);

  const auditing = cohort === "audit";
  const filtered = queuePhotos(photos, cohort, { region, review, reviewer });
  const active = filtered.find((photo) => photo.id === activeIds[cohort]) ?? filtered[0];
  const incidental = photos.filter((photo) => photo.cohort === "incidental");
  const groupable = incidental.filter((photo) => photo.encounter_linkable === true);
  const visits = new Set(groupable.map((photo) => photo.encounter_group ?? photo.id)).size;
  const ungrouped = incidental.length - groupable.length;
  const reviewed = incidental.filter((photo) => photo.review_status !== "unreviewed").length;
  const held = incidental.filter((photo) => heldForAudit(photo, reviewer)).length;

  // Time belongs to whoever is reviewing, so a shared browser does not pass it between people.
  const timerKey = [runId, auditing ? "audit" : "review", reviewer.trim(), active?.id ?? ""];
  const effort = useReviewTimer(JSON.stringify(timerKey));

  function switchRun(id: string) {
    setPhotos([]);
    setEffortSummary(undefined);
    setAuditSummary(undefined);
    setActiveIds({});
    setRunId(id);
  }

  async function submit<K extends keyof Payloads>(kind: K, fields: Payloads[K]) {
    if (!active) return false;
    const measured = effort.snapshot();
    setSaving(true);
    try {
      await request(`runs/${runId}/photos/${active.id}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...fields,
          reviewer: reviewer.trim(),
          effort_seconds: measured.seconds,
        }),
      });
      effort.clear(measured);
      setNotice(SAVED[kind]);
      await latestRefresh.current();
      return true;
    } catch (failure) {
      setError(String(failure));
      return false;
    } finally {
      setSaving(false);
    }
  }
  const save = (status: Status, note: string) => submit("review", { status, note });
  const saveAudit = (finding: string, note: string) => submit("audit", { finding, note });
  const saveFinding = (finding: NewFinding) => submit("findings", finding);
  const saveJudgement = (judgement: NewJudgement) => submit("judgements", judgement);

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
              <small>
                Independent site visits: {visits.toString().padStart(2, "0")}
                {ungrouped > 0 && ` · ${ungrouped} could not be grouped`} · background unlabelled
              </small>
            </div>
            <div>
              <span>Reviewed</span>
              <strong>
                {reviewed.toString().padStart(2, "0")}
                <em> / {incidental.length}</em>
              </strong>
              <small>{effortNote(effortSummary)}</small>
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
          <RunSettings
            runs={runs}
            runId={runId}
            createdAt={run?.created_at}
            onSwitch={switchRun}
            onStarted={(id) => {
              switchRun(id);
              setNotice("Regional run queued. Progress updates automatically.");
            }}
            onError={setError}
          />
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
                <p>
                  {auditing
                    ? "Fixed random sample · screening rank hidden"
                    : `Highest relative similarity first${held ? ` · ${held} held for blind audit` : ""}`}
                </p>
              </div>
              <div className="cohort-tabs">
                {VIEWS.map(([view, label]) => (
                  <button
                    type="button"
                    key={view}
                    aria-pressed={cohort === view}
                    onClick={() => setCohort(view)}
                  >
                    {label}
                  </button>
                ))}
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
                {!auditing && (
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
                )}
              </div>
              <div className="photo-list">
                {filtered.map((photo, index) => (
                  <button
                    type="button"
                    key={photo.id}
                    className={`photo-row ${active?.id === photo.id ? "selected" : ""}`}
                    onClick={() => {
                      setActiveIds((ids) => ({ ...ids, [cohort]: photo.id }));
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
                        {auditing
                          ? "Blind audit photo"
                          : (names[photo.scores.best_species ?? ""] ?? "Awaiting screening")}
                      </strong>
                      <span>{photo.original_common_name || photo.original_taxon}</span>
                      <small>
                        {photo.observed_on ?? "Date unknown"} ·{" "}
                        {auditing
                          ? auditedBy(photo, reviewer)
                            ? "Audited"
                            : "Not yet audited"
                          : photo.review_status === "unreviewed"
                            ? "Needs review"
                            : photo.review_status}
                        {!auditing && photo.disputed && " · Reviewers disagree"}
                        {!auditing && siteVisitNote(photo) && ` · ${siteVisitNote(photo)}`}
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
            {active && auditing ? (
              <AuditPanel
                // A save, or another auditor taking over, starts a fresh draft so no
                // auditor sees an earlier note before answering.
                key={`${runId}:audit:${active.id}:${auditedBy(active, reviewer)}`}
                photo={active}
                runId={runId}
                summary={auditSummary}
                reviewer={reviewer}
                onReviewerChange={changeReviewer}
                onSave={saveAudit}
                saving={saving}
              />
            ) : active ? (
              <Evidence
                key={`${runId}:${active.id}`}
                photo={active}
                runId={runId}
                onSave={save}
                onSaveFinding={saveFinding}
                onSaveJudgement={saveJudgement}
                saving={saving}
                references={references}
                reviewer={reviewer}
                onReviewerChange={changeReviewer}
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
            <FieldNotes species={auditing ? undefined : active?.scores.species} />
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
