"use client";

import Image from "next/image";
import { useState } from "react";
import {
  imageUrl,
  names,
  type Photo,
  type Status,
  siteVisitSummary,
  statusLabels,
} from "../lib/types";
import ReviewHistory from "./review-history";

export default function Evidence({
  photo,
  runId,
  onSave,
  saving,
  reviewer,
  onReviewerChange,
}: {
  photo: Photo;
  runId: string;
  onSave: (status: Status, note: string) => Promise<void>;
  saving: boolean;
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
  const { scores } = photo;
  const [x1, y1, x2, y2] = scores.box ?? [0, 0, 0, 0];
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
      <div className="image-stage">
        {scores.width && scores.height ? (
          <svg
            viewBox={`0 0 ${scores.width} ${scores.height}`}
            role="img"
            aria-label={`Source photo of ${photo.original_common_name || photo.original_taxon}; highlighted search window`}
          >
            <title>Original photo with an optional model search window</title>
            <image href={imageUrl(runId, photo.id)} width={scores.width} height={scores.height} />
            {windowVisible && scores.box && (
              <rect
                x={x1}
                y={y1}
                width={x2 - x1}
                height={y2 - y1}
                fill="rgba(241,204,106,.06)"
                stroke="#f1cc6a"
                strokeWidth={Math.max(scores.width / 260, 2)}
                strokeDasharray="12 6"
              />
            )}
          </svg>
        ) : (
          <Image
            src={imageUrl(runId, photo.id)}
            alt={`Original observation of ${photo.original_taxon}`}
            width={1024}
            height={1024}
            unoptimized
          />
        )}
        <span className="image-caption">
          {photo.cohort === "reference"
            ? "Reference photo · kept outside discovery results"
            : "Animal-subject photo · background plants unlabelled"}
        </span>
      </div>
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
      <ReviewHistory key={photo.review_count} runId={runId} photo={photo} />
    </article>
  );
}
