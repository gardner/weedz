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
