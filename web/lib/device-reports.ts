import type { Photo } from "./types";

/** The run that holds reports approved and sent from phones (issue #58). */
export const DEVICE_RUN = "device-reports";

export const NO_IMAGE_CONSENT =
  "No image: the person who sent this report did not consent to share it";

/** Where a device report came from and what screened it, as the API states it. */
export type DeviceProvenance = {
  submitter: number;
  report_id: string;
  received_at: string;
  captured_at: string | null;
  app_version: string;
  model_key: string;
  revision: string;
  ranking_revision: number;
  score_meaning: string | null;
  consent_wording: string;
  image_consent: boolean;
};

/** Whether the photo has an image to request: a device report only with consent. */
export const hasImage = (photo: Photo) => !photo.device || photo.device.image_consent;

/** The device's exact point with its accuracy; the location is the point of the report. */
export function exactPoint(photo: Photo): string {
  const { latitude, longitude, positional_accuracy_m: accuracy } = photo;
  if (latitude === null || longitude === null) return "No location sent";
  const within = accuracy === null ? "accuracy not sent" : `±${accuracy} m`;
  return `${latitude}, ${longitude} ${within}`;
}

/** Each provenance fact as a label and its value, in reading order. */
export function provenanceRows(photo: Photo, device: DeviceProvenance): [string, string][] {
  const licence = photo.photo_license ? photo.photo_license.toUpperCase() : "None chosen";
  return [
    ["Sent by", `Submitter ${device.submitter} (a device, not a named person)`],
    ["App", `App ${device.app_version}`],
    [
      "Screening model",
      `${device.model_key} ${device.revision}, ranking revision ${device.ranking_revision}`,
    ],
    [
      "On-device score",
      `Margin ${photo.scores.margin ?? "not sent"} (a ranking score, not a probability)`,
    ],
    ["Score meaning", device.score_meaning ?? "Not declared for this configuration"],
    ["Consent", `Consent wording ${device.consent_wording}`],
    [
      "Image licence",
      device.image_consent ? `${licence} · ${photo.attribution}` : NO_IMAGE_CONSENT,
    ],
    ["Captured", device.captured_at ?? "Capture time not sent"],
    ["Received", device.received_at],
    ["Device location", exactPoint(photo)],
  ];
}
