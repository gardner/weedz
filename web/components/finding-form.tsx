"use client";

import { useState } from "react";
import {
  type BoxDraft,
  EDGES,
  EMPTY_BOX,
  type Finding,
  type FindingKind,
  findingName,
  kindLabels,
  type NewFinding,
  type ParsedBox,
} from "../lib/findings";
import { names, type Photo } from "../lib/types";

const OTHER = "other";
const recordedAt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/**
 * Record a plant the reviewer sees: a different species from the suggestion, or one the
 * screening missed. Its box can be drawn on the photo or typed as pixel edges, so it
 * works without a pointer. Saving it does not change the reviewer's decision.
 */
export function FindingForm({
  photo,
  box,
  parsedBox: parsed,
  onBoxChange,
  blocked,
  onSave,
}: {
  photo: Photo;
  box: BoxDraft;
  parsedBox: ParsedBox;
  onBoxChange: (box: BoxDraft) => void;
  blocked: boolean;
  onSave: (finding: NewFinding) => void;
}) {
  const suggestion = photo.scores.best_species;
  const { width, height } = photo.scores;
  const [kind, setKind] = useState<FindingKind>(suggestion ? "correction" : "addition");
  const [species, setSpecies] = useState("");
  const [otherTaxon, setOtherTaxon] = useState("");
  const [note, setNote] = useState("");
  const choices = Object.entries(names).filter(
    ([scientific]) => kind === "addition" || scientific !== suggestion,
  );
  const chosen = species === OTHER || choices.some(([scientific]) => scientific === species);
  const named = chosen && (species !== OTHER || otherTaxon.trim() !== "");
  return (
    <form
      id="finding-form"
      className="finding-form"
      aria-label="Record a different or missed plant"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          kind,
          species: species === OTHER ? null : species,
          other_taxon: species === OTHER ? otherTaxon.trim() : null,
          box: parsed.box,
          note,
        });
      }}
    >
      <fieldset>
        <legend>What did you see?</legend>
        <label>
          <input
            type="radio"
            name="finding-kind"
            checked={kind === "correction"}
            disabled={!suggestion}
            onChange={() => setKind("correction")}
          />{" "}
          A different species from the suggestion
        </label>
        <label>
          <input
            type="radio"
            name="finding-kind"
            checked={kind === "addition"}
            onChange={() => setKind("addition")}
          />{" "}
          A plant the screening missed
        </label>
      </fieldset>
      <label htmlFor="finding-species">Species</label>
      <select
        id="finding-species"
        value={chosen ? species : ""}
        onChange={(event) => setSpecies(event.target.value)}
      >
        <option value="" disabled>
          Choose a species
        </option>
        {choices.map(([scientific, common]) => (
          <option key={scientific} value={scientific}>
            {common} ({scientific})
          </option>
        ))}
        <option value={OTHER}>Other taxon, typed below</option>
      </select>
      {species === OTHER && (
        <>
          <label htmlFor="finding-other">Other taxon</label>
          <input
            id="finding-other"
            value={otherTaxon}
            onChange={(event) => setOtherTaxon(event.target.value)}
            maxLength={200}
            placeholder="Scientific or common name, as you know it"
          />
        </>
      )}
      <fieldset className="box-fields" aria-describedby="box-help">
        <legend>Visible extent (optional)</legend>
        {width && height ? (
          <>
            <small id="box-help">
              Drag on the photo, or type edges in pixels. The image is {width} × {height} px.
            </small>
            <div className="edge-grid">
              {EDGES.map((edge, index) => (
                <label key={edge}>
                  {edge}
                  <input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    max={index % 2 ? height : width}
                    value={box[index]}
                    onChange={(event) =>
                      onBoxChange(
                        box.map((value, at) =>
                          at === index ? event.target.value : value,
                        ) as BoxDraft,
                      )
                    }
                  />
                </label>
              ))}
            </div>
            {parsed.error && <p className="field-error">{parsed.error}</p>}
            <button type="button" className="text-button" onClick={() => onBoxChange(EMPTY_BOX)}>
              Clear box
            </button>
          </>
        ) : (
          <small id="box-help">A box can be added once screening has measured the image.</small>
        )}
      </fieldset>
      <label htmlFor="finding-note">Finding note</label>
      <textarea
        id="finding-note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        maxLength={4000}
        placeholder="Which features did you use?"
        rows={2}
      />
      <button type="submit" className="primary" disabled={blocked || !named || !!parsed.error}>
        Save finding
      </button>
      <small>Saved with your name and time. It does not change your decision above.</small>
    </form>
  );
}

/** Recorded findings for the photo, oldest first. */
export function FindingList({ findings }: { findings: Finding[] }) {
  if (!findings.length) return null;
  return (
    <section className="recorded-findings" aria-label="Recorded plants">
      <h3>Recorded plants</h3>
      <ol>
        {findings.map((finding, index) => (
          <li key={finding.id}>
            <strong>
              {index + 1}. {kindLabels[finding.kind]}:
            </strong>{" "}
            {findingName(finding)}
            {finding.other_taxon && <em> (as typed)</em>} · {finding.reviewer}{" "}
            <time dateTime={finding.created_at}>
              {recordedAt.format(new Date(finding.created_at))}
            </time>
            {finding.box && <small> · Box {finding.box.map(Math.round).join(", ")} px</small>}
            {finding.note && <p>{finding.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
