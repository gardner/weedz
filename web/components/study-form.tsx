"use client";

import { useId, useState } from "react";
import {
  type Draft,
  fromDraft,
  type StudyDefinition,
  type StudyTerms,
  toDraft,
} from "../lib/study";

type Picks = "regions" | "species" | "lookalikes";

/** Edit a study as a whole new version: every field the study records, in one form. */
export default function StudyForm({
  terms,
  initial,
  reviewer,
  saving,
  onSave,
  onCancel,
}: {
  terms: StudyTerms;
  initial: StudyDefinition;
  reviewer: string;
  saving: boolean;
  onSave: (definition: StudyDefinition, author: string, note: string) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState<Draft>(() => toDraft(initial, terms));
  const [author, setAuthor] = useState(reviewer);
  const [note, setNote] = useState("");
  const result = fromDraft(draft);
  const problem = typeof result === "string" ? result : "";
  const set = (fields: Partial<Draft>) => setDraft((current) => ({ ...current, ...fields }));
  const pick = (kind: Picks, name: string, fields: Partial<Draft[Picks][string]>) =>
    setDraft((current) => ({
      ...current,
      [kind]: { ...current[kind], [name]: { ...current[kind][name], ...fields } },
    }));
  const text = (label: string, key: keyof Draft, hint = "", rows = 0) => {
    const value = draft[key] as string;
    const change = (next: string) => set({ [key]: next } as Partial<Draft>);
    const field = `${id}-${key}`;
    const described = hint ? `${field}-hint` : undefined;
    return (
      <div className="study-field">
        <label htmlFor={field}>{label}</label>
        {hint && <small id={described}>{hint}</small>}
        {rows ? (
          <textarea
            id={field}
            rows={rows}
            value={value}
            aria-describedby={described}
            onChange={(event) => change(event.target.value)}
          />
        ) : (
          <input
            id={field}
            value={value}
            aria-describedby={described}
            onChange={(event) => change(event.target.value)}
          />
        )}
      </div>
    );
  };
  const choices = (kind: Picks, names: string[], common: Record<string, string> = {}) =>
    names.map((name) => (
      <div className="study-pick" key={name}>
        <label className="study-check">
          <input
            type="checkbox"
            checked={draft[kind][name]?.on ?? false}
            onChange={(event) => pick(kind, name, { on: event.target.checked })}
          />
          {name}
          {common[name] && ` (${common[name]})`}
        </label>
        <label>
          Why {name}
          <input
            value={draft[kind][name]?.why ?? ""}
            onChange={(event) => pick(kind, name, { why: event.target.value })}
          />
        </label>
      </div>
    ));

  return (
    <form
      className="study-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (typeof result !== "string") onSave(result, author.trim(), note.trim());
      }}
    >
      <fieldset>
        <legend>Question and people</legend>
        <label>
          Status
          <select
            value={draft.status}
            onChange={(event) => set({ status: event.target.value as Draft["status"] })}
          >
            <option value="provisional">Provisional: not yet agreed with the partner</option>
            <option value="agreed">Agreed with the partner</option>
          </select>
        </label>
        {text("Discovery question", "question", "What the partner wants answered", 2)}
        {text("Partner", "partner", "Who would act on a discovery")}
        {text("Responsible people", "people", "One per line, as Role: Name", 3)}
      </fieldset>
      <fieldset>
        <legend>Area and period</legend>
        {choices("regions", terms.regions)}
        {text("Not yet screened regions", "otherRegions", "One per line, as Region: why", 2)}
        <div className="study-pick">
          <label>
            Period start
            <input
              type="date"
              value={draft.periodStart}
              onChange={(event) => set({ periodStart: event.target.value })}
            />
          </label>
          <label>
            Period end
            <input
              type="date"
              value={draft.periodEnd}
              onChange={(event) => set({ periodEnd: event.target.value })}
            />
          </label>
        </div>
        {text("Why this period", "periodWhy", "", 2)}
      </fieldset>
      <fieldset>
        <legend>Watchlist and lookalikes</legend>
        {choices("species", Object.keys(terms.species), terms.species)}
        {text("Not yet screened species", "otherSpecies", "One per line, as Species: why", 2)}
        {choices(
          "lookalikes",
          terms.lookalikes.map((item) => item.name),
          Object.fromEntries(
            terms.lookalikes.map((item) => [item.name, `looks like ${item.confusable_with}`]),
          ),
        )}
        {text("Not yet screened lookalikes", "otherLookalikes", "One per line, as Taxon: why", 2)}
      </fieldset>
      <fieldset>
        <legend>Collection, budget and reference records</legend>
        {text("Source collection", "source", "", 2)}
        {text("Original-subject selection", "selection", "How the photos' subjects were chosen", 2)}
        <div className="study-pick">
          <label>
            Review hours
            <input
              type="number"
              min={0}
              step="any"
              value={draft.hours}
              onChange={(event) => set({ hours: event.target.value })}
            />
          </label>
          <label>
            Review photos
            <input
              type="number"
              min={0}
              value={draft.photos}
              onChange={(event) => set({ photos: event.target.value })}
            />
          </label>
        </div>
        {text("Budget note", "budgetNote")}
        {text("Reference records", "references", "One per line, as Name: coverage note", 2)}
      </fieldset>
      <fieldset>
        <legend>Success limits (leave blank until agreed)</legend>
        {Object.entries(terms.limits).map(([key, limit]) => (
          <div className="study-pick" key={key}>
            <label>
              {limit.measure}: {limit.direction} … {limit.unit}
              <input
                type="number"
                min={0}
                step="any"
                value={draft.limits[key]?.value ?? ""}
                onChange={(event) =>
                  set({
                    limits: {
                      ...draft.limits,
                      [key]: { ...draft.limits[key], value: event.target.value },
                    },
                  })
                }
              />
            </label>
            <label>
              Note on {limit.measure}
              <input
                value={draft.limits[key]?.note ?? ""}
                onChange={(event) =>
                  set({
                    limits: {
                      ...draft.limits,
                      [key]: { ...draft.limits[key], note: event.target.value },
                    },
                  })
                }
              />
            </label>
          </div>
        ))}
      </fieldset>
      <fieldset>
        <legend>Record this version</legend>
        <label>
          Recorded by
          <input value={author} onChange={(event) => setAuthor(event.target.value)} />
        </label>
        <label>
          What changed and why
          <input value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
      </fieldset>
      {problem && (
        <p className="study-problem" role="alert">
          {problem}
        </p>
      )}
      <div className="study-actions">
        <button type="submit" className="primary" disabled={saving || !!problem || !author.trim()}>
          {saving ? "Saving…" : "Save study version"}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
