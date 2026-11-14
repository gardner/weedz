"use client";

import { useState } from "react";
import {
  DIMENSIONS,
  type Dimension,
  type NewJudgement,
  NOTE_REQUIRED,
  unavailable,
  valueLabel,
} from "../lib/judgements";
import type { Photo } from "../lib/types";

type Save = (judgement: NewJudgement) => Promise<boolean>;

/**
 * Identity, location usefulness, historical relevance and novelty, each judged and saved
 * on its own so one can be settled while another stays disputed or unassessed.
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
  return (
    <section className="judgements" aria-labelledby="judgements-heading">
      <h3 id="judgements-heading">Separate judgements</h3>
      <p className="judgements-intro">
        Each is saved on its own with your name, and none changes your decision above. Leave a
        dimension unassessed rather than guess.
      </p>
      {DIMENSIONS.map(({ key }) => (
        <JudgementRow
          key={key}
          dimension={key}
          photo={photo}
          reviewer={reviewer}
          blocked={blocked}
          onSave={onSave}
        />
      ))}
    </section>
  );
}

function JudgementRow({
  dimension,
  photo,
  reviewer,
  blocked,
  onSave,
}: {
  dimension: Dimension;
  photo: Photo;
  reviewer: string;
  blocked: boolean;
  onSave: Save;
}) {
  const info = DIMENSIONS.find((item) => item.key === dimension) ?? DIMENSIONS[0];
  const standing = Object.entries(photo.judgements?.[dimension] ?? {});
  const own = photo.judgements?.[dimension]?.[reviewer.trim()]?.value;
  // Derived, not initial state, because the remembered name arrives after mount.
  const [draft, setValue] = useState<string | null>(null);
  const value = draft ?? own ?? "unassessed";
  const [note, setNote] = useState("");
  const id = `judgement-${dimension}`;
  const required = NOTE_REQUIRED[`${dimension}:${value}`];
  const missing = Boolean(required) && !note.trim();
  const unsupported = info.values
    .map(([key, label]) => [label, unavailable(photo, dimension, key)] as const)
    .filter(([, reason]) => reason);
  return (
    <div className="judgement">
      <label htmlFor={id}>{info.label}</label>
      <small id={`${id}-help`}>{info.question}</small>
      {photo.judgement_disputes?.includes(dimension) && (
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
            <option key={key} value={key} disabled={Boolean(unavailable(photo, dimension, key))}>
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
            if (await onSave({ dimension, value, note })) setNote("");
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
