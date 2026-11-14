import type { Photo } from "./types";

export type View = "incidental" | "reference" | "audit";

export const VIEWS: [View, string][] = [
  ["incidental", "Incidental photos"],
  ["reference", "References"],
  ["audit", "Audit sample"],
];

/** A sampled photo stays out of ranked review until audited, so its audit stays blind. */
export const heldForAudit = (photo: Photo) => Boolean(photo.audit_sample && !photo.audited);

/** Photos listed in a view. The audit list uses a neutral order that hides screening rank. */
export function queuePhotos(photos: Photo[], view: View, region: string, review: string): Photo[] {
  const inRegion = (photo: Photo) => region === "all" || photo.region === region;
  if (view === "audit") {
    return photos
      .filter((photo) => photo.audit_sample && inRegion(photo))
      .sort((a, b) => a.id.localeCompare(b.id));
  }
  return photos
    .filter(
      (photo) =>
        photo.cohort === view &&
        !heldForAudit(photo) &&
        inRegion(photo) &&
        (review === "all" || photo.review_status === review),
    )
    .sort((a, b) => (b.scores.margin ?? -2) - (a.scores.margin ?? -2));
}
