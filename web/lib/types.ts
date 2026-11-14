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
  review_note: string;
  encounter_group?: string;
  encounter_size?: number;
  encounter_linkable?: boolean;
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
