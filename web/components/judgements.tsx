"use client";

import { useState } from "react";
import { findingName, kindLabels } from "../lib/findings";
import {
  DIMENSIONS,
  type Dimension,
  type Judged,
  type NewJudgement,
  NOTE_REQUIRED,
  unavailable,
  valueLabel,
} from "../lib/judgements";
import { names, type Photo } from "../lib/types";

type Save = (judgement: NewJudgement) => Promise<boolean>;

const SUGGESTION = "suggestion";
type Plant = { key: string; label: string; taxon: string | null; judged: Judged };

/**
 * Identity, location usefulness, historical relevance and novelty, each judged and saved
 * on its own so one can be settled while another stays disputed or unassessed. Each
 * judgement is about one plant: the suggested species or a recorded plant.
 */
export default function JudgementPanel({
  photo,
  reviewer,
  blocked,
  onSave,
}: {
  photo: Photo;
  reviewer: string;
  blocked: boolean;
  onSave: Save;
}) {
  const suggestion = photo.scores.best_species;
  // Numbered as in the "Recorded plants" list, so plants of the same kind and taxon differ.
  const plants: Plant[] = (photo.findings ?? []).map((plant, index) => ({
    key: String(plant.id),
    label: `Recorded plant ${index + 1}: ${kindLabels[plant.kind]}, ${findingName(plant)} (${plant.reviewer})`,
    taxon: plant.species,
    judged: plant,
  }));
  if (suggestion) {
    const label = `Suggested: ${names[suggestion] ?? suggestion}`;
    plants.unshift({ key: SUGGESTION, label, taxon: suggestion, judged: photo });
  }
  const [chosen, setChosen] = useState(SUGGESTION);
  const plant = plants.find(({ key }) => key === chosen) ?? plants[0];
  return (
    <section className="judgements" aria-labelledby="judgements-heading">
      <h3 id="judgements-heading">Separate judgements</h3>
      <p className="judgements-intro">
        Each is saved on its own with your name, and none changes your decision above. Leave a
        dimension unassessed rather than guess.
      </p>
      {plant ? (
        <>
          <label className="judgement-target" htmlFor="judgement-target">
            Plant being judged
          </label>
          <select
            id="judgement-target"
            value={plant.key}
            onChange={(event) => setChosen(event.target.value)}
          >
            {plants.map(({ key, label }) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          {DIMENSIONS.map(({ key }) => (
            <JudgementRow
              // A draft belongs to one plant and one reviewer; either changing starts afresh.
              key={`${plant.key}:${reviewer.trim()}:${key}`}
              dimension={key}
              photo={photo}
              findingId={plant.key === SUGGESTION ? null : Number(plant.key)}
              taxon={plant.taxon}
              judged={plant.judged}
              reviewer={reviewer}
              blocked={blocked}
              onSave={onSave}
            />
          ))}
        </>
      ) : (
        <p className="judgements-intro">
          Nothing to judge yet: screening has not suggested a plant and none is recorded.
        </p>
      )}
    </section>
  );
}

function JudgementRow({
  dimension,
  photo,
  findingId,
  taxon,
  judged,
  reviewer,
  blocked,
  onSave,
}: {
  dimension: Dimension;
  photo: Photo;
  findingId: number | null;
  taxon: string | null;
  judged: Judged;
  reviewer: string;
  blocked: boolean;
  onSave: Save;
}) {
  const info = DIMENSIONS.find((item) => item.key === dimension) ?? DIMENSIONS[0];
  const standing = Object.entries(judged.judgements?.[dimension] ?? {});
  const own = judged.judgements?.[dimension]?.[reviewer.trim()]?.value;
  const [draft, setValue] = useState<string | null>(null);
  const value = draft ?? own ?? "unassessed";
  const [note, setNote] = useState("");
  const id = `judgement-${dimension}`;
  const required = NOTE_REQUIRED[`${dimension}:${value}`];
  const missing = Boolean(required) && !note.trim();
  const unsupported = info.values
    .map(([key, label]) => [label, unavailable(photo, taxon, dimension, key)] as const)
    .filter(([, reason]) => reason);
  return (
    <div className="judgement">
      <label htmlFor={id}>{info.label}</label>
      <small id={`${id}-help`}>{info.question}</small>
      {judged.judgement_disputes?.includes(dimension) && (
        <p className="judgement-dispute">
          <strong>⚠ Reviewers disagree</strong>
        </p>
      )}
      <ul className="judgement-standing">
        {standing.length ? (
          standing.map(([name, judgement]) => (
            <li key={name}>
              <strong>{name}:</strong> {valueLabel(dimension, judgement.value)}
              {judgement.note && <span> · {judgement.note}</span>}
            </li>
          ))
        ) : (
          <li>Not assessed yet</li>
        )}
      </ul>
      <div className="judgement-controls">
        <select
          id={id}
          value={value}
          aria-describedby={`${id}-help`}
          onChange={(event) => setValue(event.target.value)}
        >
          {info.values.map(([key, label]) => (
            <option
              key={key}
              value={key}
              disabled={Boolean(unavailable(photo, taxon, dimension, key))}
            >
              {label}
            </option>
          ))}
        </select>
        <input
          id={`${id}-note`}
          aria-label={`${info.label} note`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={4000}
          placeholder={required ? "Required: give your evidence" : "Reason (optional)"}
        />
        <button
          type="button"
          disabled={blocked || missing}
          onClick={async () => {
            if (await onSave({ finding_id: findingId, dimension, value, note })) setNote("");
          }}
        >
          Save {info.label.toLowerCase()}
        </button>
      </div>
      {required && <small className="judgement-required">{required}</small>}
      {unsupported.map(([label, reason]) => (
        <small key={label}>
          {label} is unavailable: {reason}.
        </small>
      ))}
    </div>
  );
}
