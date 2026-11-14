import type { Photo } from "./types";

export type Dimension = "identity" | "location" | "history" | "novelty";

/** A reviewer's latest standing judgement on one dimension. */
export type Standing = { value: string; note: string; created_at: string };
export type Judgements = Record<Dimension, Record<string, Standing>>;
export type NewJudgement = { dimension: Dimension; value: string; note: string };

type DimensionInfo = {
  key: Dimension;
  label: string;
  question: string;
  values: [value: string, label: string][];
};

const UNASSESSED: [string, string] = ["unassessed", "Not assessed"];

/** Mirrors `weedz.discovery.judgements.JUDGEMENTS`; each dimension can stay unassessed. */
export const DIMENSIONS: DimensionInfo[] = [
  {
    key: "identity",
    label: "Identity",
    question: "Do the diagnostic features settle what the plant is?",
    values: [
      ["confirmed", "Confirmed"],
      ["disputed", "Disputed"],
      ["unresolved", "Unresolved: needs more evidence"],
      UNASSESSED,
    ],
  },
  {
    key: "location",
    label: "Location usefulness",
    question: "Could this location guide a follow-up visit to the plant?",
    values: [
      ["usable", "Usable for follow-up"],
      ["too_imprecise", "Too imprecise"],
      ["camera_point_only", "Camera point only: plant position unknown"],
      ["unknown", "Unknown"],
      UNASSESSED,
    ],
  },
  {
    key: "history",
    label: "Historical relevance",
    question: "What does the photo date say about the plant today?",
    values: [
      ["recent_evidence", "Recent evidence: current presence not verified"],
      ["historical_evidence", "Historical evidence: current presence unknown"],
      ["no_longer_present", "Reported no longer present"],
      ["date_unknown", "Date unknown"],
      UNASSESSED,
    ],
  },
  {
    key: "novelty",
    label: "Novelty",
    question: "How new is this finding, and compared with what?",
    values: [
      ["already_recorded", "Already recorded here"],
      ["new_in_photo", "Newly noticed in this photo"],
      ["absent_from_references", "Absent from the reference records"],
      ["earlier_than_records", "Earlier than the available records"],
      ["verified_new_locality", "Independently verified new locality"],
      UNASSESSED,
    ],
  },
];

/** Claims that need the reviewer's reason in the note. */
export const NOTE_REQUIRED: Record<string, string> = {
  "novelty:verified_new_locality":
    "A verified new locality needs the verification evidence: who checked, how and when.",
  "identity:unresolved": "Say what additional evidence would resolve the identity.",
  "history:no_longer_present": "Say who reported the plant gone, and when.",
};

const located = (photo: Photo) => photo.coordinate_status === "public" && photo.latitude != null;
const dated = (photo: Photo) => Boolean(photo.observed_on);
const compared = (photo: Photo) =>
  Object.values(photo.reference_comparison ?? {}).some((comparison) => comparison.comparable);
const UNDATED = "the photo date is unknown";
const UNCOMPARED = "no reference records can be compared with this photo";
const REQUIREMENTS: Record<string, [(photo: Photo) => boolean, string][]> = {
  "location:usable": [[located, "the observation location is obscured or missing"]],
  "history:recent_evidence": [[dated, UNDATED]],
  "history:historical_evidence": [[dated, UNDATED]],
  "novelty:absent_from_references": [[compared, UNCOMPARED]],
  "novelty:earlier_than_records": [
    [dated, UNDATED],
    [compared, UNCOMPARED],
  ],
};

/** Why this photo cannot support a value, mirroring the API's check; null when it can. */
export function unavailable(photo: Photo, dimension: Dimension, value: string): string | null {
  const unmet = (REQUIREMENTS[`${dimension}:${value}`] ?? []).find(([met]) => !met(photo));
  return unmet ? unmet[1] : null;
}

export function valueLabel(dimension: Dimension, value: string): string {
  const info = DIMENSIONS.find((item) => item.key === dimension);
  return info?.values.find(([key]) => key === value)?.[1] ?? value;
}
