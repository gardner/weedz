/**
 * A photo's location and date limits, computed in Python (weedz.discovery.limits).
 * A search area is centred where the photographer was; it is never a plant location.
 */
export type SearchArea = {
  status: "searchable" | "obscured" | "missing" | "accuracy_unknown";
  reason: string;
  centre: [number, number] | null;
  centre_is: string;
  accuracy_m: number | null;
  allowance_m: number;
  allowance_reason: string;
  radius_m: number | null;
  site_context: boolean;
};

export type PhotoDates = {
  photographed: string | null;
  uploaded: string | null;
  screened: string;
  days_photo_to_upload: number | null;
  days_photo_to_screening: number | null;
  current_presence: string;
};

export type Limits = { search_area: SearchArea; dates: PhotoDates };

const NOT_SEARCHABLE: Record<Exclude<SearchArea["status"], "searchable">, string> = {
  obscured: "Not searchable: obscured location",
  missing: "Not searchable: no location",
  accuracy_unknown: "Not searchable: accuracy not supplied",
};

export function searchAreaHeadline(area: SearchArea): string {
  if (area.status === "searchable") return `${area.radius_m} m radius around the observation point`;
  return NOT_SEARCHABLE[area.status];
}

/** The observation point, labelled as the photographer's position, or null when not public. */
export function observationPoint(
  area: SearchArea,
  latitude: number | null,
  longitude: number | null,
) {
  if (area.status === "obscured" || latitude === null || longitude === null) return null;
  return `Observation point ${latitude.toFixed(3)}, ${longitude.toFixed(3)} is where the photographer was, not the plant.`;
}

/** Why the area has this radius, or why there is none; a reported accuracy is kept. */
export function searchAreaBasis(area: SearchArea, reportedAccuracy: number | null): string {
  if (area.status !== "searchable") {
    const accuracy = reportedAccuracy === null ? "" : ` Reported accuracy ±${reportedAccuracy} m.`;
    return `${area.reason}.${accuracy}`;
  }
  const context = area.site_context
    ? " Accurate enough for aerial site context, not to place the plant."
    : "";
  return `Reported accuracy ±${area.accuracy_m} m + ${area.allowance_m} m allowance: no camera bearing or pose is recorded, so the plant may lie in any direction.${context}`;
}

const after = (days: number | null) =>
  days === null ? "" : ` (${days} day${days === 1 ? "" : "s"} after the photo)`;

/** Capture, upload and screening dates, kept apart, with their gaps from the photo. */
export function dateLines(dates: PhotoDates): string[] {
  return [
    `Uploaded ${dates.uploaded ?? "unknown"}${after(dates.days_photo_to_upload)}`,
    `Screened ${dates.screened}${after(dates.days_photo_to_screening)}`,
  ];
}
