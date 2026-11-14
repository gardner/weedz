import { needsSpecialist, waitingSince } from "./referrals";
import type { Photo } from "./types";

export type View = "incidental" | "reference" | "lookalike" | "audit" | "specialist";

export const VIEWS: [View, string][] = [
  ["incidental", "Incidental photos"],
  ["reference", "References"],
  ["lookalike", "Lookalikes"],
  ["audit", "Audit sample"],
  ["specialist", "Needs specialist"],
];

/** Whether this reviewer has audited the photo. Names are unauthenticated, as for reviews. */
export const auditedBy = (photo: Photo, reviewer: string) =>
  (photo.auditors ?? []).includes(reviewer.trim());

/**
 * A sampled photo stays out of each reviewer's ranked queue until they have audited it,
 * so no auditor sees its suggestion first. Without a name, every sampled photo is held.
 */
export const heldForAudit = (photo: Photo, reviewer: string) =>
  Boolean(photo.audit_sample) && !auditedBy(photo, reviewer);

/**
 * Photos listed in a view. The audit list uses a neutral order that hides screening rank.
 * Open referrals list longest waiting first, from every cohort and any review status,
 * still holding back any sampled photo this reviewer has not audited.
 */
export function queuePhotos(
  photos: Photo[],
  view: View,
  filters: { region: string; review: string; reviewer: string },
): Photo[] {
  const { region, review, reviewer } = filters;
  const inRegion = (photo: Photo) => region === "all" || photo.region === region;
  if (view === "audit") {
    return photos
      .filter((photo) => photo.audit_sample && inRegion(photo))
      .sort((a, b) => a.id.localeCompare(b.id));
  }
  const inView = view === "specialist" ? needsSpecialist : (photo: Photo) => photo.cohort === view;
  const order =
    view === "specialist"
      ? (a: Photo, b: Photo) => waitingSince(a).localeCompare(waitingSince(b))
      : (a: Photo, b: Photo) => (b.scores.margin ?? -2) - (a.scores.margin ?? -2);
  return photos
    .filter(
      (photo) =>
        inView(photo) &&
        !heldForAudit(photo, reviewer) &&
        inRegion(photo) &&
        // Referred photos have usually been reviewed already, so status never hides one.
        (view === "specialist" || review === "all" || photo.review_status === review),
    )
    .sort(order);
}
