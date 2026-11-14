import { findingName, kindLabels } from "./findings";
import { names, type Photo } from "./types";

export type LeadAction = "selected" | "deselected";

/** Who selected a lead for follow-up, and why; the latest appended event stands. */
export type Lead = { selector: string; reason: string; created_at: string };

/** A photo's selected leads: its suggestion, and recorded plants by finding id. */
export type PhotoLeads = { suggestion: Lead | null; plants: Record<string, Lead> };

export type NewLeadEvent = { finding_id: number | null; action: LeadAction; reason: string };

export const SUGGESTION = "suggestion";

export type LeadTarget = {
  key: string;
  findingId: number | null;
  label: string;
  lead: Lead | null;
};

/** The suggestion (when screened) and each recorded plant, numbered as in "Recorded plants". */
export function leadTargets(photo: Photo): LeadTarget[] {
  const selected = photo.lead ?? { suggestion: null, plants: {} };
  const suggested = photo.scores.best_species;
  const suggestion: LeadTarget[] = suggested
    ? [
        {
          key: SUGGESTION,
          findingId: null,
          label: `Suggested species: ${names[suggested] ?? suggested}`,
          lead: selected.suggestion,
        },
      ]
    : [];
  return [
    ...suggestion,
    ...(photo.findings ?? []).map((plant, index) => ({
      key: String(plant.id),
      findingId: plant.id,
      label: `Recorded plant ${index + 1}: ${kindLabels[plant.kind]}, ${findingName(plant)}`,
      lead: selected.plants[String(plant.id)] ?? null,
    })),
  ];
}
