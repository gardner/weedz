"use client";

import Image from "next/image";
import { useState } from "react";
import { type AuditSummary, imageUrl, names, type Photo } from "../lib/types";

/**
 * Blind audit of a sampled photo. Deliberately shows no screening suggestion, search
 * window or score, so the reviewer looks at the whole scene rather than where the model
 * pointed. This is how missed weeds are found.
 */
export default function AuditPanel({
  photo,
  runId,
  summary,
  reviewer,
  onReviewerChange,
  onSave,
  saving,
}: {
  photo: Photo;
  runId: string;
  summary?: AuditSummary;
  reviewer: string;
  onReviewerChange: (name: string) => void;
  onSave: (finding: string, note: string) => Promise<void>;
  saving: boolean;
}) {
  const [note, setNote] = useState("");
  const blocked = saving || !reviewer.trim();
  return (
    <article className="evidence audit-panel">
      <div className="evidence-heading">
        <div>
          <span className="eyebrow">BLIND AUDIT · {photo.region.toUpperCase()}</span>
          <h2>Is any watchlist weed visible?</h2>
          <p className="scientific">
            {summary
              ? `${summary.audited} of ${summary.sampled} sampled photos audited`
              : "Audit sample"}
          </p>
        </div>
        <span className="badge">{photo.audited ? "Audited" : "Not yet audited"}</span>
      </div>
      <div className="image-stage">
        <Image
          src={imageUrl(runId, photo.id)}
          alt={`Original observation of ${photo.original_common_name || photo.original_taxon}`}
          width={1024}
          height={1024}
          unoptimized
        />
        <span className="image-caption">
          Random audit photo · screening suggestion hidden on purpose
        </span>
      </div>
      <p className="attribution">
        {photo.attribution} · {photo.photo_license.toUpperCase()} ·{" "}
        <a href={imageUrl(runId, photo.id)} target="_blank" rel="noreferrer">
          Open full image ↗
        </a>
      </p>
      <div className="review-form">
        <p>
          Search the whole photo, including edges and background, for any of the watchlist species.
          This sample was chosen at random, not by the model.
        </p>
        <label htmlFor="auditor-name">Your name</label>
        <input
          id="auditor-name"
          className="reviewer-name"
          value={reviewer}
          onChange={(event) => onReviewerChange(event.target.value)}
          maxLength={80}
          autoComplete="name"
        />
        <label htmlFor="audit-note">Audit note</label>
        <textarea
          id="audit-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={4000}
          placeholder="Where in the photo? What features did you use?"
          rows={3}
        />
        <div className="decision-buttons">
          {Object.entries(names).map(([scientific, common]) => (
            <button
              type="button"
              key={scientific}
              disabled={blocked}
              onClick={() => onSave(scientific, note)}
            >
              {common}
            </button>
          ))}
          <button type="button" disabled={blocked} onClick={() => onSave("none", note)}>
            None visible
          </button>
          <button type="button" disabled={blocked} onClick={() => onSave("unsure", note)}>
            Unsure
          </button>
        </div>
        <small>Audits are saved separately from suggestion reviews, with your name and time.</small>
      </div>
    </article>
  );
}
