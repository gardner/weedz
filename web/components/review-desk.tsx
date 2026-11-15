"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DEVICE_RUN } from "../lib/device-reports";
import type { NewFinding } from "../lib/findings";
import type { NewJudgement } from "../lib/judgements";
import type { NewLeadEvent } from "../lib/leads";
import { auditedBy, defaultView, heldForAudit, queuePhotos, VIEWS, type View } from "../lib/queue";
import { type Closing, type NewReferral, needsSpecialist } from "../lib/referrals";
import { useReviewTimer } from "../lib/review-timer";
import { useReviewer } from "../lib/reviewer";
import type { ScoreMeaning } from "../lib/score-meaning";
import type { Study } from "../lib/study";
import {
  type AuditSummary,
  effortNote,
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
import { Thumbnail } from "./photo-stage";
import RunSettings from "./run-settings";
import { ScreeningNote } from "./score-meaning";
import StudyPanel from "./study-panel";
import SuitabilityPanel from "./suitability-panel";

type Payloads = {
  review: { status: Status; note: string };
  audit: { finding: string; note: string };
  findings: NewFinding;
  judgements: NewJudgement;
  referrals: NewReferral & { referrer: string };
  answered: Closing & { actor: string };
  withdrawn: Closing & { actor: string };
  leads: NewLeadEvent & { selector: string };
};
const SAVED: Record<keyof Payloads, string> = {
  review: "Review saved locally.",
  audit: "Audit saved locally.",
  findings: "Finding saved locally.",
  judgements: "Judgement saved locally.",
  referrals: "Referral saved locally.",
  answered: "Referral answer saved locally.",
  withdrawn: "Referral withdrawal saved locally.",
  leads: "Follow-up selection saved locally.",
};
// Choosing what to follow up is not timed: its time stays with the next timed action.
const UNTIMED = new Set<keyof Payloads>(["leads"]);

/** With `signedInAs`, the API requires tokens and every record carries that name. */
export default function ReviewDesk({
  signedInAs,
  onSignOut,
}: {
  signedInAs?: string;
  onSignOut?: () => void;
}) {
  const requestGeneration = useRef(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [references, setReferences] = useState<References>(null);
  const [effortSummary, setEffortSummary] = useState<ReviewEffort>();
  const [auditSummary, setAuditSummary] = useState<AuditSummary>();
  const [study, setStudy] = useState<Study | null>(null);
  const [scoreMeaning, setScoreMeaning] = useState<ScoreMeaning>();
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
  const [reviewer, changeReviewer] = useReviewer(signedInAs);
  const run = runs.find((item) => item.id === runId);

  const refresh = useCallback(async () => {
    const generation = ++requestGeneration.current;
    try {
      const list = await request<Run[]>("runs");
      if (generation !== requestGeneration.current) return;
      setRuns(list);
      const selected = runId || list[0]?.id;
      if (selected) {
        if (!runId) {
          setRunId(selected);
          setCohort(defaultView(selected));
        }
        const result = await request<RunDetail>(`runs/${selected}`);
        if (generation !== requestGeneration.current) return;
        setPhotos(result.photos);
        setEffortSummary(result.review_effort);
        setAuditSummary(result.audit);
        setReferences(result.references ?? null);
        setStudy(result.study ?? null);
        setScoreMeaning(result.score_meaning);
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
  const specialist = cohort === "specialist";
  const held = (specialist ? photos.filter(needsSpecialist) : incidental).filter((photo) =>
    heldForAudit(photo, reviewer),
  ).length;

  // Time belongs to whoever is reviewing, so a shared browser does not pass it between people.
  const timerKey = [runId, auditing ? "audit" : "review", reviewer.trim(), active?.id ?? ""];
  const effort = useReviewTimer(JSON.stringify(timerKey));

  function switchRun(id: string) {
    setPhotos([]);
    setEffortSummary(undefined);
    setAuditSummary(undefined);
    setStudy(null);
    setScoreMeaning(undefined);
    setActiveIds({});
    setCohort(defaultView(id));
    setRunId(id);
  }

  async function submit<K extends keyof Payloads>(
    kind: K,
    fields: Payloads[K],
    path: string = kind,
  ) {
    if (!active) return false;
    const measured = effort.snapshot();
    const timed = !UNTIMED.has(kind);
    setSaving(true);
    try {
      await request(`runs/${runId}/photos/${active.id}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          timed
            ? { ...fields, reviewer: reviewer.trim(), effort_seconds: measured.seconds }
            : fields,
        ),
      });
      if (timed) effort.clear(measured);
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
  const name = reviewer.trim();
  const refer = (referral: NewReferral) => submit("referrals", { ...referral, referrer: name });
  const closeReferral = (id: number, closing: Closing) =>
    submit(closing.action, { ...closing, actor: name }, `referrals/${id}/events`);
  const selectLead = (event: NewLeadEvent) => submit("leads", { ...event, selector: name });

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
        {signedInAs && (
          <div className="signed-in">
            Signed in as <strong>{signedInAs}</strong>
            <button type="button" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        )}
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
              <div className="export-buttons">
                <a className="button export-button" href={`/api/runs/${runId}/package/archive`}>
                  Follow-up package ↓
                </a>
                <a className="button export-button" href={`/api/runs/${runId}/export`}>
                  Export evidence ↓
                </a>
              </div>
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
          <StudyPanel
            key={runId}
            runId={runId}
            study={study}
            reviewer={reviewer}
            locked={!changeReviewer}
            onSaved={async (message) => {
              setNotice(message);
              await latestRefresh.current();
            }}
            onError={setError}
          />
          {/* Suitability measures a sampled run; device reports are not one (#123). */}
          {runId !== DEVICE_RUN && <SuitabilityPanel key={`suitability:${runId}`} runId={runId} />}
          <ScreeningNote meaning={scoreMeaning} />
          <div className="workspace">
            <section className="queue" aria-label="Photo review queue">
              <div className="queue-heading">
                <h2>
                  Review queue <span>{filtered.length}</span>
                </h2>
                <p>
                  {auditing
                    ? "Fixed random sample · screening rank hidden"
                    : `${specialist ? "Open referrals, longest waiting first" : "Highest relative similarity first"}${held ? ` · ${held} held for blind audit` : ""}`}
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
                {!auditing && !specialist && (
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
                    <Thumbnail photo={photo} runId={runId} />
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
                        {!auditing && needsSpecialist(photo) && " · Needs specialist"}
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
                onRefer={refer}
                onCloseReferral={closeReferral}
                onSelectLead={selectLead}
                saving={saving}
                references={references}
                scoreMeaning={scoreMeaning}
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
            <FieldNotes />
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
