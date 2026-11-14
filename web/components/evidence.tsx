"use client";

import { useState } from "react";
import { type BoxDraft, EMPTY_BOX, type NewFinding, parseBox } from "../lib/findings";
import type { NewJudgement } from "../lib/judgements";
import type { Closing, NewReferral } from "../lib/referrals";
import {
  imageUrl,
  names,
  type Photo,
  type References,
  referenceNote,
  type Status,
  siteVisitSummary,
  statusLabels,
} from "../lib/types";
import { FindingForm, FindingList } from "./finding-form";
import JudgementPanel from "./judgements";
import PhotoStage from "./photo-stage";
import ReferralPanel from "./referrals";
import ReviewHistory from "./review-history";

export default function Evidence({
  photo,
  runId,
  onSave,
  onSaveFinding,
  onSaveJudgement,
  onRefer,
  onCloseReferral,
  saving,
  references,
  reviewer,
  onReviewerChange,
}: {
  photo: Photo;
  runId: string;
  onSave: (status: Status, note: string) => Promise<unknown>;
  onSaveFinding: (finding: NewFinding) => Promise<boolean>;
  onSaveJudgement: (judgement: NewJudgement) => Promise<boolean>;
  onRefer: (referral: NewReferral) => Promise<boolean>;
  onCloseReferral: (referralId: number, closing: Closing) => Promise<boolean>;
  saving: boolean;
  references: References;
  reviewer: string;
  onReviewerChange: (name: string) => void;
}) {
  // Only the latest note's author gets it back to edit; others start blank. Derived, not
  // initial state, because the remembered name arrives after mount.
  const ownNote =
    photo.review_reviewer && photo.review_reviewer === reviewer.trim() ? photo.review_note : "";
  const [draft, setNote] = useState<string | null>(null);
  const note = draft ?? ownNote;
  const [windowVisible, setWindowVisible] = useState(true);
  const [recording, setRecording] = useState(false);
  const [box, setBox] = useState<BoxDraft>(EMPTY_BOX);
  const { scores } = photo;
  const parsedBox = parseBox(box, scores.width, scores.height);
  function toggleRecording(open: boolean) {
    setRecording(open);
    setBox(EMPTY_BOX);
  }
  const target = scores.best_species ?? "Pending screening";
  const blocked = saving || !reviewer.trim();
  return (
    <article className="evidence">
      <div className="evidence-heading">
        <div>
          <span className="eyebrow">PHOTO EVIDENCE · {photo.region.toUpperCase()}</span>
          <h2>{names[target] ?? target}</h2>
          <p className="scientific">{scores.best_species ?? "Waiting for the worker"}</p>
        </div>
        <span className={`badge ${photo.review_status}`}>
          {photo.review_status === "unreviewed" ? "Needs review" : photo.review_status}
        </span>
      </div>
      {photo.disputed && (
        <div className="dispute" role="note">
          <strong>⚠ Reviewers disagree</strong>
          <ul>
            {Object.entries(photo.reviewer_decisions).map(([name, status]) => (
              <li key={name}>
                {name}: {statusLabels[status] ?? status}
              </li>
            ))}
          </ul>
        </div>
      )}
      <PhotoStage
        photo={photo}
        runId={runId}
        windowVisible={windowVisible}
        drawing={recording}
        draft={recording ? parsedBox.box : null}
        onDraw={(drawn) => setBox(drawn.map(String) as BoxDraft)}
      />
      <div className="image-tools">
        <label>
          <input
            type="checkbox"
            checked={windowVisible}
            onChange={(event) => setWindowVisible(event.target.checked)}
          />{" "}
          Show search window
        </label>
        <a href={imageUrl(runId, photo.id)} target="_blank" rel="noreferrer">
          Open full image ↗
        </a>
      </div>
      <p className="attribution">
        {photo.attribution} · {photo.photo_license.toUpperCase()} ·{" "}
        <a href={photo.source_url} target="_blank" rel="noreferrer">
          View on iNaturalist ↗
        </a>
      </p>
      <div className="context-grid">
        <div>
          <span>Original subject</span>
          <strong>{photo.original_common_name || photo.original_taxon}</strong>
          <small>{photo.original_taxon}</small>
        </div>
        <div>
          <span>Photographed</span>
          <strong>{photo.observed_on ?? "Date unknown"}</strong>
          <small>Uploaded {photo.uploaded_at?.slice(0, 10) ?? "unknown"}</small>
        </div>
        <div>
          <span>Site visit</span>
          <strong>{siteVisitSummary(photo)}</strong>
          <small>Same observer, date and nearby location; not necessarily the same plant</small>
        </div>
        <div>
          <span>Observation location</span>
          <strong>
            {photo.coordinate_status === "missing"
              ? "Not available"
              : photo.coordinate_status === "obscured"
                ? "Obscured location"
                : `${photo.latitude?.toFixed(3)}, ${photo.longitude?.toFixed(3)}`}
          </strong>
          <small>
            {photo.positional_accuracy_m
              ? `Reported accuracy ±${photo.positional_accuracy_m} m`
              : "Accuracy not supplied"}
          </small>
        </div>
        <div>
          <span>Known records</span>
          <strong>{referenceNote(photo, references)}</strong>
          <small>
            {references
              ? `${references.dataset.title}, snapshot as of ${references.retrieved_at.slice(0, 10)}. Distance between reported points; a missing record is not evidence of a new locality.`
              : "Run `uv run main.py references` to load DOC weed records for comparison."}{" "}
            An unexpected location is a reason to refer to a specialist, not to reject.
          </small>
        </div>
      </div>
      <div className="review-form">
        <h3>Is the suggested species visible?</h3>
        <p>
          Check leaf shape, flowers and context. The dashed window is a search area, not a plant
          boundary.
        </p>
        <label htmlFor="reviewer-name">Your name</label>
        <input
          id="reviewer-name"
          value={reviewer}
          onChange={(event) => onReviewerChange(event.target.value)}
          maxLength={80}
          autoComplete="name"
          aria-describedby="reviewer-help"
        />
        <small id="reviewer-help">
          Recorded with each decision on this computer. Required before deciding.
        </small>
        <label htmlFor="review-note">Review note</label>
        <textarea
          id="review-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={4000}
          placeholder="What supports your decision? What would resolve uncertainty?"
          rows={3}
        />
        <div className="decision-buttons">
          <button
            type="button"
            className="primary"
            disabled={blocked || !scores.best_species}
            onClick={() => onSave("confirmed", note)}
          >
            Species visible
          </button>
          <button type="button" disabled={blocked} onClick={() => onSave("rejected", note)}>
            Reject suggestion
          </button>
          <button type="button" disabled={blocked} onClick={() => onSave("uncertain", note)}>
            Unsure
          </button>
        </div>
        {photo.review_status !== "unreviewed" && (
          <button
            type="button"
            className="text-button"
            disabled={blocked}
            onClick={() => onSave("unreviewed", note)}
          >
            Reopen for review
          </button>
        )}
        <small>
          Saved locally with review history. “Visible” records a reviewer decision about this image;
          it does not establish a new weed locality.
        </small>
      </div>
      <div className="finding-section">
        <button
          type="button"
          aria-expanded={recording}
          aria-controls={recording ? "finding-form" : undefined}
          onClick={() => toggleRecording(!recording)}
        >
          Record a different or missed plant
        </button>
        {recording && (
          <FindingForm
            photo={photo}
            box={box}
            parsedBox={parsedBox}
            onBoxChange={setBox}
            blocked={blocked}
            onSave={async (finding) => {
              if (await onSaveFinding(finding)) toggleRecording(false);
            }}
          />
        )}
        <FindingList findings={photo.findings ?? []} />
      </div>
      <JudgementPanel
        photo={photo}
        reviewer={reviewer}
        blocked={blocked}
        onSave={onSaveJudgement}
      />
      <ReferralPanel
        photo={photo}
        reviewer={reviewer}
        blocked={blocked}
        onRefer={onRefer}
        onClose={onCloseReferral}
      />
      <ReviewHistory key={photo.review_count} runId={runId} photo={photo} />
    </article>
  );
}
