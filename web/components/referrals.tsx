"use client";

import { useState } from "react";
import {
  type Action,
  type Closing,
  citable,
  isOpen,
  type NewReferral,
  REASONS,
  type Reason,
  type Referral,
  reasonLabel,
  statusLabels,
  targetLabel,
} from "../lib/referrals";
import type { Photo } from "../lib/types";

type Refer = (referral: NewReferral) => Promise<boolean>;
type Close = (referralId: number, closing: Closing) => Promise<boolean>;

const WHOLE_PHOTO = "photo";
const eventLabels: Record<Action, string> = { answered: "Answered", withdrawn: "Withdrawn" };

/**
 * Requests for specialist assessment, each with a reason, and their answers. A referral
 * and its answer are separate attributed records: neither changes a reviewer's decision.
 */
export default function ReferralPanel({
  photo,
  reviewer,
  blocked,
  onRefer,
  onClose,
}: {
  photo: Photo;
  reviewer: string;
  blocked: boolean;
  onRefer: Refer;
  onClose: Close;
}) {
  const [referring, setReferring] = useState(false);
  const referrals = photo.referrals ?? [];
  return (
    <section className="referrals" aria-labelledby="referrals-heading">
      <h3 id="referrals-heading">Specialist referrals</h3>
      <p className="judgements-intro">
        Refer a lookalike, a cultivated-or-wild question, a poor view or a doubtful location or date
        to someone with the right expertise. A referral changes no decision or judgement.
      </p>
      {referrals.length ? (
        <ol className="referral-list">
          {referrals.map((referral, index) => (
            <ReferralItem
              // A response draft belongs to one reviewer; another name starts afresh.
              key={`${referral.id}:${reviewer.trim()}`}
              number={index + 1}
              photo={photo}
              referral={referral}
              reviewer={reviewer}
              blocked={blocked}
              onClose={onClose}
            />
          ))}
        </ol>
      ) : (
        <p className="judgements-intro">No referrals yet.</p>
      )}
      <button
        type="button"
        aria-expanded={referring}
        aria-controls={referring ? "referral-form" : undefined}
        onClick={() => setReferring(!referring)}
      >
        Refer for specialist assessment
      </button>
      {referring && (
        <ReferralForm
          photo={photo}
          blocked={blocked}
          onRefer={async (referral) => {
            const saved = await onRefer(referral);
            if (saved) setReferring(false);
            return saved;
          }}
        />
      )}
    </section>
  );
}

function ReferralForm({
  photo,
  blocked,
  onRefer,
}: {
  photo: Photo;
  blocked: boolean;
  onRefer: Refer;
}) {
  const [target, setTarget] = useState(WHOLE_PHOTO);
  const [reason, setReason] = useState<Reason | "">("");
  const [expertise, setExpertise] = useState("");
  const [note, setNote] = useState("");
  return (
    <div id="referral-form" className="referral-form">
      <label htmlFor="referral-target">Plant referred</label>
      <select id="referral-target" value={target} onChange={(e) => setTarget(e.target.value)}>
        <option value={WHOLE_PHOTO}>{targetLabel(photo, null)}</option>
        {(photo.findings ?? []).map((plant) => (
          <option key={plant.id} value={plant.id}>
            {targetLabel(photo, plant.id)}
          </option>
        ))}
      </select>
      <label htmlFor="referral-reason">Reason</label>
      <select
        id="referral-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value as Reason)}
      >
        <option value="" disabled>
          Choose a reason
        </option>
        {REASONS.map(([key, label]) => (
          <option key={key} value={key}>
            {label}
          </option>
        ))}
      </select>
      <label htmlFor="referral-expertise">Expertise needed</label>
      <input
        id="referral-expertise"
        value={expertise}
        onChange={(e) => setExpertise(e.target.value)}
        maxLength={200}
        placeholder="For example, a Clematis specialist"
      />
      <label htmlFor="referral-note">What is unresolved?</label>
      <textarea
        id="referral-note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={4000}
        rows={3}
        placeholder="Required: what is unresolved, and what would settle it"
      />
      <button
        type="button"
        className="primary"
        disabled={blocked || !reason || !note.trim()}
        onClick={() =>
          reason &&
          onRefer({
            finding_id: target === WHOLE_PHOTO ? null : Number(target),
            reason,
            expertise,
            note,
          })
        }
      >
        Send referral
      </button>
    </div>
  );
}

function ReferralItem({
  number,
  photo,
  referral,
  reviewer,
  blocked,
  onClose,
}: {
  number: number;
  photo: Photo;
  referral: Referral;
  reviewer: string;
  blocked: boolean;
  onClose: Close;
}) {
  const id = `referral-${referral.id}`;
  return (
    <li className="referral">
      <div className="referral-heading">
        <strong>Referral {number}</strong>
        <span className={`referral-status ${referral.status}`}>
          {statusLabels[referral.status]}
        </span>
      </div>
      <p>
        {targetLabel(photo, referral.finding_id)} · {reasonLabel(referral.reason)} · Expertise:{" "}
        {referral.expertise || "not specified"}
      </p>
      <p>{referral.note}</p>
      <small>
        Referred by {referral.referrer} on {referral.created_at.slice(0, 10)}
      </small>
      {referral.events.map((event) => (
        <p key={event.id} className="referral-event">
          {`${eventLabels[event.action]} by ${event.actor} on ${event.created_at.slice(0, 10)}: ${event.note}`}
          {event.judgement_ids.length > 0 &&
            ` (informed ${event.judgement_ids.length} judgement${event.judgement_ids.length === 1 ? "" : "s"})`}
        </p>
      ))}
      {isOpen(referral) && (
        <Response
          id={id}
          number={number}
          photo={photo}
          referral={referral}
          reviewer={reviewer}
          blocked={blocked}
          onClose={onClose}
        />
      )}
    </li>
  );
}

function Response({
  id,
  number,
  photo,
  referral,
  reviewer,
  blocked,
  onClose,
}: {
  id: string;
  number: number;
  photo: Photo;
  referral: Referral;
  reviewer: string;
  blocked: boolean;
  onClose: Close;
}) {
  const [note, setNote] = useState("");
  const [cited, setCited] = useState<number[]>([]);
  const options = citable(photo, referral, reviewer);
  const close = (action: Action) =>
    onClose(referral.id, {
      action,
      note,
      judgement_ids:
        action === "answered" ? cited.filter((c) => options.some((o) => o.id === c)) : [],
    });
  return (
    <div className="referral-response">
      <label htmlFor={`${id}-response`}>Response to referral {number}</label>
      <textarea
        id={`${id}-response`}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={4000}
        rows={2}
        placeholder="Required: your assessment, or why the referral is withdrawn"
      />
      {options.length > 0 && (
        <fieldset>
          <legend>Judgements this answer informed</legend>
          {options.map((option) => (
            <label key={option.id}>
              <input
                type="checkbox"
                checked={cited.includes(option.id)}
                onChange={(e) =>
                  setCited((ids) =>
                    e.target.checked ? [...ids, option.id] : ids.filter((c) => c !== option.id),
                  )
                }
              />{" "}
              {option.label}
            </label>
          ))}
        </fieldset>
      )}
      <div className="decision-buttons">
        <button
          type="button"
          className="primary"
          disabled={blocked || !note.trim()}
          onClick={() => close("answered")}
        >
          Record answer
        </button>
        <button type="button" disabled={blocked || !note.trim()} onClick={() => close("withdrawn")}>
          Withdraw referral
        </button>
      </div>
    </div>
  );
}
