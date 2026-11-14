import { findingName, kindLabels } from "./findings";
import { DIMENSIONS, type Judged, valueLabel } from "./judgements";
import type { Photo } from "./types";

export type Reason =
  | "lookalike"
  | "cultivated_or_wild"
  | "poor_view"
  | "location_or_date"
  | "other";
export type Action = "answered" | "withdrawn";

export type ReferralEvent = {
  id: number;
  action: Action;
  actor: string;
  note: string;
  judgement_ids: number[];
  created_at: string;
};

/** A request for specialist assessment; its status comes from its append-only events. */
export type Referral = {
  id: number;
  finding_id: number | null;
  reason: Reason;
  expertise: string;
  note: string;
  referrer: string;
  created_at: string;
  status: "open" | Action;
  events: ReferralEvent[];
};

export type NewReferral = Pick<Referral, "finding_id" | "reason" | "expertise" | "note">;
export type Closing = { action: Action; note: string; judgement_ids: number[] };

/** Mirrors `weedz.discovery.referrals.REASONS`. */
export const REASONS: [Reason, string][] = [
  ["lookalike", "Native or other lookalike"],
  ["cultivated_or_wild", "Cultivated or wild?"],
  ["poor_view", "Poor view"],
  ["location_or_date", "Location or date in question"],
  ["other", "Other (see note)"],
];

export const reasonLabel = (reason: Reason) =>
  REASONS.find(([key]) => key === reason)?.[1] ?? reason;

export const statusLabels: Record<Referral["status"], string> = {
  open: "Open",
  answered: "Answered",
  withdrawn: "Withdrawn",
};

export const isOpen = (referral: Referral) => referral.status === "open";

export const needsSpecialist = (photo: Photo) => (photo.referrals ?? []).some(isOpen);

/** When the photo's longest-waiting open referral was made; empty when none is open. */
export const waitingSince = (photo: Photo) =>
  (photo.referrals ?? [])
    .filter(isOpen)
    .map((referral) => referral.created_at)
    .sort()[0] ?? "";

/** The referred plant, numbered as in "Recorded plants"; null refers the whole photo. */
export function targetLabel(photo: Photo, findingId: number | null): string {
  if (findingId === null) return "Whole photo";
  const plants = photo.findings ?? [];
  const index = plants.findIndex((plant) => plant.id === findingId);
  if (index < 0) return "A recorded plant";
  const plant = plants[index];
  return `Recorded plant ${index + 1}: ${kindLabels[plant.kind]}, ${findingName(plant)}`;
}

export type Citable = { id: number; label: string };

/**
 * Standing judgements an answer may cite: the answerer's own, on the referred plant (any
 * plant for the whole photo) and made since the referral, mirroring the API's check.
 */
export function citable(photo: Photo, referral: Referral, reviewer: string): Citable[] {
  const plants = photo.findings ?? [];
  // A whole-photo referral may cite judgements on any plant, so each is named.
  const judged: [Judged, string][] =
    referral.finding_id === null
      ? [
          [photo, ""],
          ...plants.map((plant, index): [Judged, string] => [
            plant,
            `Recorded plant ${index + 1} · `,
          ]),
        ]
      : plants.filter((plant) => plant.id === referral.finding_id).map((plant) => [plant, ""]);
  return judged.flatMap(([plant, prefix]) =>
    DIMENSIONS.flatMap(({ key, label }) =>
      Object.entries(plant.judgements?.[key] ?? {}).flatMap(([name, standing]) =>
        standing.id != null &&
        name === reviewer.trim() &&
        standing.created_at >= referral.created_at
          ? [
              {
                id: standing.id,
                label: `${prefix}${label}: ${valueLabel(key, standing.value)} (${name})`,
              },
            ]
          : [],
      ),
    ),
  );
}
