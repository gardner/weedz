import type { Photo } from "./types";

/** Source labels are observation subjects, never identifications inferred by this model. */
export function sourceSubject(
  photo: Pick<Photo, "cohort" | "original_common_name" | "original_taxon">,
): string {
  return photo.cohort === "device"
    ? "Device report"
    : photo.original_common_name || photo.original_taxon || "Source photo";
}

/** Positive means only an advantage over the configured comparison labels, not detection. */
export function watchlistHint(
  scores: { best_species?: string; margin?: number },
  declared: boolean,
  labels: Record<string, string> = {},
): string {
  if (!scores.best_species) return "Awaiting screening";
  if (!Object.hasOwn(labels, scores.best_species)) return "Unrecognized watchlist comparison";
  if (!declared) return "Screening result has no declared interpretation";
  if (typeof scores.margin !== "number" || !Number.isFinite(scores.margin))
    return "Screening comparison unavailable";
  if (scores.margin <= 0) return "No positive watchlist match";
  return `Model hint: ${labels[scores.best_species] ?? scores.best_species} · needs review`;
}

/** A device meaning stamp is preserved, never interpreted as the desktop comparison rule. */
export function photoHint(photo: Photo, declared: boolean, labels: Record<string, string>): string {
  if (photo.cohort === "device")
    return photo.device?.score_meaning
      ? "Device model result · see recorded score meaning"
      : "Screening result has no declared interpretation";
  return watchlistHint(photo.scores, declared, labels);
}
