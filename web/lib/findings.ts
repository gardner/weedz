import type { Judged } from "./judgements";
import { names } from "./types";

export type FindingKind = "correction" | "addition";

/** A reviewer's corrected or missed plant. Free-text taxa are kept as typed. */
export type Finding = Judged & {
  id: number;
  kind: FindingKind;
  species: string | null;
  other_taxon: string | null;
  box: number[] | null;
  note: string;
  reviewer: string;
  created_at: string;
};

export type NewFinding = Pick<Finding, "kind" | "species" | "other_taxon" | "box" | "note">;

export const kindLabels: Record<FindingKind, string> = {
  correction: "Different species",
  addition: "Missed plant",
};

/** Left, top, right and bottom edges in image pixels, as typed or drawn. */
export type BoxDraft = [string, string, string, string];
export const EMPTY_BOX: BoxDraft = ["", "", "", ""];
export const EDGES = ["Left", "Top", "Right", "Bottom"] as const;

export function findingName(finding: Pick<Finding, "species" | "other_taxon">): string {
  if (finding.species) return names[finding.species] ?? finding.species;
  return finding.other_taxon ?? "Unnamed";
}

export type ParsedBox = { box: number[] | null; error?: string };

/**
 * A box from its four edges: none when all are blank (or the image size is unknown),
 * otherwise every edge is needed, ordered and inside the image. Gives the reason when
 * it is not usable.
 */
export function parseBox(draft: BoxDraft, width?: number, height?: number): ParsedBox {
  if (!width || !height || draft.every((edge) => edge.trim() === "")) return { box: null };
  const box = draft.map((edge) => (edge.trim() === "" ? Number.NaN : Number(edge)));
  if (box.some((edge) => !Number.isFinite(edge) || edge < 0)) {
    return { box: null, error: "Enter all four edges as pixels, or clear the box" };
  }
  const [left, top, right, bottom] = box;
  if (left >= right) return { box: null, error: "Left must be less than right" };
  if (top >= bottom) return { box: null, error: "Top must be less than bottom" };
  if (right > width || bottom > height) {
    return { box: null, error: `The box must fit the ${width} × ${height} px image` };
  }
  return { box };
}
