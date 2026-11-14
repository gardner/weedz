/** The declared meaning of a run's screening scores, for its model and ranking revision. */
export type ScoreMeaning = {
  declared: boolean;
  id: string | null;
  model_key: string | null;
  ranking_revision?: number;
  meaning_version?: number;
  calibrated: boolean;
  score: string;
  use: string;
  not_meaning: string[];
  /** Plain-language rules, null until a meaning version declares one. */
  operating_point: string | null;
  abstention: string | null;
  choosing_an_operating_point: string;
  evidence: { key: string; finding: string; source: string; labels: string }[];
  run_evidence: string;
};

const MODEL_NAMES: Record<string, string> = { bioclip: "BioCLIP", "bioclip-2": "BioCLIP 2" };

/** The run's model by name, or a generic name when the run has not recorded one. */
export function modelName(meaning: ScoreMeaning | undefined): string {
  const key = meaning?.model_key;
  return key ? (MODEL_NAMES[key] ?? key) : "The screening model";
}

/** Which declaration applies, e.g. "BioCLIP 2 · ranking revision 4 · meaning 1". */
export function meaningLabel(meaning: ScoreMeaning | undefined): string {
  if (!meaning?.declared) return "No declared meaning for this screening configuration";
  return `${modelName(meaning)} · ranking revision ${meaning.ranking_revision} · meaning ${meaning.meaning_version}`;
}

/** A margin in words: how far the weed is above or below the strongest comparison label. */
export function marginWords(margin: number): string {
  if (margin === 0) return "0.000, level with the strongest comparison label";
  const side = margin > 0 ? "above" : "below";
  // A margin too small to show keeps its sign: it still orders the queue.
  if (Math.abs(margin) < 0.0005) return `less than 0.001 ${side} the strongest comparison label`;
  const size = Math.abs(margin).toFixed(3);
  return `${margin > 0 ? "+" : "−"}${size} ${side} the strongest comparison label`;
}
