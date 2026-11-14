import type { Finding } from "./findings";
import type { Judged } from "./judgements";
import type { PhotoLeads } from "./leads";
import type { Limits } from "./limits";
import type { Referral } from "./referrals";
import type { Study } from "./study";

export type Status = "unreviewed" | "confirmed" | "rejected" | "uncertain";
export type Run = {
  id: string;
  status: string;
  detail: string;
  created_at: string;
  spec: { limit_per_region: number; controls_per_species: number; before: string };
};
export type Photo = Judged & {
  id: string;
  region: string;
  cohort: "incidental" | "reference" | "lookalike";
  lookalike_taxon?: string | null;
  lookalike_of?: string | null;
  reference_species: string | null;
  original_taxon: string;
  original_common_name: string;
  source_url: string;
  attribution: string;
  photo_license: string;
  observation_license: string;
  observed_on: string | null;
  uploaded_at: string | null;
  latitude: number | null;
  longitude: number | null;
  positional_accuracy_m: number | null;
  coordinate_status: string;
  review_status: Status;
  audit_sample?: boolean;
  audited?: boolean;
  auditors?: string[];
  review_note: string;
  review_reviewer: string;
  reviewer_decisions: Record<string, Status>;
  disputed: boolean;
  review_count: number;
  encounter_group?: string;
  encounter_size?: number;
  encounter_linkable?: boolean;
  reference_comparison?: Record<string, ReferenceComparison>;
  limits?: Limits;
  findings?: Finding[];
  referrals?: Referral[];
  lead?: PhotoLeads;
  scores: {
    best_species?: string;
    similarity?: number;
    margin?: number;
    box?: number[];
    width?: number;
    height?: number;
    species?: { name: string; similarity: number; margin: number; box: number[] }[];
  };
};

export type ReferenceComparison = {
  comparable: boolean;
  reason?: string;
  nearest?: { gbif_key: number; distance_m: number; year: number | null } | null;
  within_radius?: number;
  radius_m?: number;
  earliest_year?: number | null;
  undated_within_radius?: number;
};

export type References = { retrieved_at: string; dataset: { title: string } } | null;

/** Distance and date to known records for the suggested species; never a novelty claim. */
export function referenceNote(photo: Photo, references: References): string {
  const species = photo.scores.best_species;
  if (!references) return "No reference snapshot loaded";
  const comparison = species ? photo.reference_comparison?.[species] : undefined;
  if (!species || !comparison) return "Awaiting screening";
  if (!comparison.comparable) return `Not compared: ${comparison.reason}`;
  const common = names[species] ?? species;
  if (!comparison.nearest) return `No DOC record of ${common} in the snapshot`;
  const km = (comparison.nearest.distance_m / 1000).toFixed(1);
  return `Nearest DOC record of ${common}: ${km} km (${comparison.nearest.year ?? "year unknown"})`;
}

export function siteVisitNote(photo: Photo): string | null {
  const others = (photo.encounter_size ?? 1) - 1;
  if (others < 1) return null;
  return `Same site visit as ${others} other photo${others === 1 ? "" : "s"}`;
}

export const unknownSiteVisit =
  "Site visit unknown: location obscured, missing, imprecise or of unknown accuracy, or date unknown";

/** Describe a photo's site visit; an unchecked visit is unknown, never independent. */
export function siteVisitSummary(photo: Photo): string {
  if (photo.encounter_linkable !== true) return unknownSiteVisit;
  return siteVisitNote(photo) ?? "No other photos from this visit";
}

/** Audit counts only; per-photo findings are in the export, so the audit view stays blind. */
export type AuditSummary = {
  sampled: number;
  audited: number;
  remaining: number;
  weed_found: number;
  found_as_top_suggestion: number;
  found_not_top_suggestion: number;
  disputed: number;
  not_blind: number;
};

export type RunDetail = {
  run: Run;
  photos: Photo[];
  review_effort?: ReviewEffort;
  audit?: AuditSummary;
  references?: References;
  study?: Study | null;
};

export type ReviewEffort = {
  total_minutes: number;
  measured_decisions: number;
  unmeasured_decisions: number;
  measured_findings?: number;
  unmeasured_findings?: number;
  measured_judgements?: number;
  unmeasured_judgements?: number;
  measured_referral_actions?: number;
  unmeasured_referral_actions?: number;
};

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

/**
 * Measured time on decisions, findings, judgements and referral actions; untimed ones are
 * listed, never zero.
 */
export function effortNote(effort: ReviewEffort | undefined): string {
  const untimed = [
    [effort?.unmeasured_decisions ?? 0, "decision"],
    [effort?.unmeasured_findings ?? 0, "finding"],
    [effort?.unmeasured_judgements ?? 0, "judgement"],
    [effort?.unmeasured_referral_actions ?? 0, "referral action"],
  ] as const;
  const timed =
    (effort?.measured_decisions ?? 0) +
    (effort?.measured_findings ?? 0) +
    (effort?.measured_judgements ?? 0) +
    (effort?.measured_referral_actions ?? 0);
  if (!effort || (!timed && untimed.every(([count]) => !count))) return "No review time yet";
  return [
    `${effort.total_minutes} min measured review time`,
    ...untimed
      .filter(([count]) => count)
      .map(([count, noun]) => `${plural(count, noun)} not timed`),
  ].join(" · ");
}

export type ReviewEvent = {
  id: number;
  reviewer: string;
  status: Status;
  note: string;
  created_at: string;
};

export const statusLabels: Record<Status, string> = {
  unreviewed: "Needs review",
  confirmed: "Species visible",
  rejected: "Rejected",
  uncertain: "Uncertain",
};

export const names: Record<string, string> = {
  "Clematis vitalba": "Old man's beard",
  "Cortaderia selloana": "Pampas grass",
  "Ulex europaeus": "Gorse",
};

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, { cache: "no-store", ...options });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(errorMessage(error.detail) ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

/** FastAPI validation errors put a list of `{ msg }` objects in `detail`. */
function errorMessage(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  return undefined;
}

export function imageUrl(runId: string, photoId: string) {
  return `/api/runs/${runId}/photos/${photoId}/image`;
}
