"use client";

import { type ReactNode, useEffect, useState } from "react";
import {
  budgetText,
  EMPTY,
  limitText,
  type Study,
  type StudyDefinition,
  type StudyTerms,
} from "../lib/study";
import { request } from "../lib/types";
import StudyForm from "./study-form";

const NOT_YET = "Not yet recorded";

function named(items: { rationale: string; screened: boolean }[], name: (index: number) => string) {
  if (!items.length) return NOT_YET;
  return items
    .map((item, index) => {
      const why = item.rationale ? `: ${item.rationale}` : "";
      return `${name(index)}${item.screened ? "" : " (not yet screened)"}${why}`;
    })
    .join("; ");
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p>{empty}</p>;
  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function StudyView({ study, terms }: { study: Study; terms?: StudyTerms }) {
  const d: StudyDefinition = study.definition;
  const use = study.budget_use;
  const period =
    d.period_start || d.period_end
      ? `${d.period_start ?? "open"} to ${d.period_end ?? "open"}${d.period_rationale ? `: ${d.period_rationale}` : ""}`
      : NOT_YET;
  const rows: [string, ReactNode][] = [
    [
      "Status",
      d.status === "agreed"
        ? "Agreed with the partner"
        : "Provisional: not yet agreed with the partner",
    ],
    ["Question", d.question || "Not yet agreed"],
    ["Partner", d.partner || "Not yet agreed"],
    ["People", d.people.map((p) => `${p.role}: ${p.name}`).join("; ") || NOT_YET],
    ["Regions", named(d.regions, (i) => d.regions[i].name)],
    ["Period", period],
    ["Watchlist", named(d.watchlist, (i) => d.watchlist[i].species)],
    ["Lookalikes", named(d.lookalikes, (i) => d.lookalikes[i].taxon)],
    ["Source collection", d.source_collection || NOT_YET],
    ["Subject selection", d.subject_selection || NOT_YET],
    [
      "Review budget",
      use
        ? [budgetText(use.hours, "h"), budgetText(use.photos, "photos"), d.review_budget.note]
            .filter(Boolean)
            .join(" · ")
        : NOT_YET,
    ],
    [
      "Reference records",
      d.reference_records.map((r) => (r.note ? `${r.name}: ${r.note}` : r.name)).join("; ") ||
        NOT_YET,
    ],
  ];
  const limits = terms
    ? Object.entries(terms.limits).map(([key, item]) => {
        const note = d.limits[key]?.note;
        return `${limitText(item, d.limits[key])}${note ? ` (${note})` : ""}`;
      })
    : [];
  return (
    <div className="study-view">
      <dl>
        {rows.map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <h2>Success limits</h2>
      <List items={limits} empty="Loading the outcome measures…" />
      <h2>Open decisions</h2>
      <List items={study.open_decisions} empty="None: every field is recorded." />
      <h2>Differs from the screening</h2>
      <List items={study.differences} empty="No difference from what the screening covers." />
      <p>
        Version {study.version} by {study.author}, {study.created_at.slice(0, 10)}
        {study.change_note && ` · ${study.change_note}`}
      </p>
    </div>
  );
}

/** The run's study: what it asks, its bounds and limits, and edits saved as new versions. */
export default function StudyPanel({
  runId,
  study,
  reviewer,
  onSaved,
  onError,
}: {
  runId: string;
  study: Study | null;
  reviewer: string;
  onSaved: (message: string) => Promise<void> | void;
  onError: (message: string) => void;
}) {
  const [terms, setTerms] = useState<StudyTerms>();
  // The version an edit started from (null for a new study); undefined when not editing.
  // Saving names it, so a version saved meanwhile is refused rather than replaced.
  const [base, setBase] = useState<{ id: string; version: number } | null>();
  const editing = base !== undefined;
  const [saving, setSaving] = useState(false);
  // Who last recorded a version here, for the next edit when no reviewer name is set.
  const [lastAuthor, setLastAuthor] = useState("");
  useEffect(() => {
    request<StudyTerms>("studies/terms")
      .then(setTerms)
      .catch((failure) => onError(String(failure)));
  }, [onError]);

  async function save(definition: StudyDefinition, author: string, note: string) {
    const post = (path: string, body: object) =>
      request<{ id: string; version: number }>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    setSaving(true);
    try {
      const edit = { definition, author, base_version: base?.version ?? 0, change_note: note };
      // A new study is linked to this run in the same request.
      const saved = base
        ? await post(`studies/${base.id}/versions`, edit)
        : await post("studies", { ...edit, run_id: runId });
      setBase(undefined);
      setLastAuthor(author);
      await onSaved(`Study version ${saved.version} saved locally.`);
    } catch (failure) {
      onError(String(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <details className="study-panel">
      <summary>
        Study definition{" "}
        <span>
          {study ? `${study.definition.status} · version ${study.version}` : "Not recorded"}
        </span>
      </summary>
      {editing && terms ? (
        <StudyForm
          terms={terms}
          initial={study?.definition ?? EMPTY}
          reviewer={reviewer.trim() || lastAuthor}
          saving={saving}
          onSave={save}
          onCancel={() => setBase(undefined)}
        />
      ) : (
        <>
          {study ? (
            <StudyView study={study} terms={terms} />
          ) : (
            <p>
              No study is recorded for this run. Its question, partner, review budget and success
              limits are not agreed in the product, so outcomes have no verdicts.
            </p>
          )}
          <button
            type="button"
            disabled={!runId || !terms}
            onClick={() => setBase(study ? { id: study.id, version: study.version } : null)}
          >
            {study ? "Edit study" : "Record the study"}
          </button>
        </>
      )}
    </details>
  );
}
