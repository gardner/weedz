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
  reference_comparison?: Record<string, ReferenceComparison>;
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
