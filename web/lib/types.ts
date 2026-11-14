export type Status = "unreviewed" | "confirmed" | "rejected" | "uncertain";
export type Run = {
  id: string;
  status: string;
  detail: string;
  created_at: string;
  spec: { limit_per_region: number; controls_per_species: number; before: string };
};
export type Photo = {
  id: string;
  region: string;
  cohort: "incidental" | "reference";
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
  review_note: string;
  review_reviewer: string;
  reviewer_decisions: Record<string, Status>;
  disputed: boolean;
  review_count: number;
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

/** Audit counts only; per-photo findings are in the export, so the audit view stays blind. */
export type AuditSummary = {
  sampled: number;
  audited: number;
  remaining: number;
  weed_found: number;
  found_as_top_suggestion: number;
  found_not_top_suggestion: number;
  disputed: number;
};

export type RunDetail = {
  run: Run;
  photos: Photo[];
  review_effort?: ReviewEffort;
  audit?: AuditSummary;
};

export type ReviewEffort = {
  total_minutes: number;
  measured_decisions: number;
  unmeasured_decisions: number;
};

export function effortNote(effort: ReviewEffort | undefined): string {
  if (!effort?.measured_decisions && !effort?.unmeasured_decisions) return "No review time yet";
  const untimed = effort.unmeasured_decisions;
  const note = `${effort.total_minutes} min measured review time`;
  return untimed ? `${note} · ${untimed} decision${untimed === 1 ? "" : "s"} not timed` : note;
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
    throw new Error(error.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function imageUrl(runId: string, photoId: string) {
  return `/api/runs/${runId}/photos/${photoId}/image`;
}
