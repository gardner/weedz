"use client";

import { useState } from "react";
import { leadTargets, type NewLeadEvent } from "../lib/leads";
import type { Photo } from "../lib/types";

type Select = (event: NewLeadEvent) => Promise<boolean>;

/**
 * Select the suggestion or a recorded plant as a lead worth follow-up, saying why. Only
 * selected leads go into the follow-up package; a deselection is a later event, not an edit.
 */
export default function LeadPanel({
  photo,
  blocked,
  onSelect,
}: {
  photo: Photo;
  blocked: boolean;
  onSelect: Select;
}) {
  const targets = leadTargets(photo);
  const [key, setKey] = useState(targets[0]?.key ?? "");
  const [reason, setReason] = useState("");
  const target = targets.find((item) => item.key === key) ?? targets[0];
  const selected = targets.filter((item) => item.lead);
  if (!target) return null;
  const action = target.lead ? "deselected" : "selected";
  return (
    <section className="referrals" aria-labelledby="leads-heading">
      <h3 id="leads-heading">Follow-up</h3>
      <p className="judgements-intro">
        Select a plant worth investigating and say why. Only selected leads go into the follow-up
        package, with their evidence and limits.
      </p>
      {selected.length ? (
        <ul className="referral-list">
          {selected.map((item) => (
            <li key={item.key} className="referral">
              <strong>{item.label}</strong>
              <p>
                Selected by {item.lead?.selector} on {item.lead?.created_at.slice(0, 10)}:{" "}
                {item.lead?.reason}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="judgements-intro">Not selected for follow-up.</p>
      )}
      <div className="referral-form">
        <label htmlFor="lead-target">Lead</label>
        <select id="lead-target" value={target.key} onChange={(e) => setKey(e.target.value)}>
          {targets.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
              {item.lead ? " (selected)" : ""}
            </option>
          ))}
        </select>
        <label htmlFor="lead-reason">{target.lead ? "Why deselect?" : "Why follow up?"}</label>
        <textarea
          id="lead-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={4000}
          rows={2}
          placeholder="Required: what makes this worth, or no longer worth, a follow-up"
        />
        <button
          type="button"
          className={target.lead ? undefined : "primary"}
          disabled={blocked || !reason.trim()}
          onClick={async () => {
            const event = { finding_id: target.findingId, action, reason } as const;
            if (await onSelect(event)) setReason("");
          }}
        >
          {target.lead ? "Deselect" : "Select for follow-up"}
        </button>
      </div>
    </section>
  );
}
