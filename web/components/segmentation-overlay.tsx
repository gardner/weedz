"use client";

import { watchlistHint } from "../lib/photo-labels";
import { names } from "../lib/types";

export type RegionEvidence = {
  id: string;
  box: number[];
  context_box: number[];
  mask_png: string;
  mask_quality: { predicted_iou: number; stability_score: number };
  views: Record<string, { best_species: string; margin: number }>;
};

export type SegmentationEvidence = {
  status: "ok" | "empty" | "failed";
  baseline_retained: boolean;
  regions: RegionEvidence[];
};

export function SegmentationMask({
  region,
  width,
  height,
}: {
  region: RegionEvidence | undefined;
  width: number;
  height: number;
}) {
  if (!region || region.mask_png.length > 1_000_000 || !/^[A-Za-z0-9+/=]+$/.test(region.mask_png))
    return null;
  return (
    <image
      href={`data:image/png;base64,${region.mask_png}`}
      width={width}
      height={height}
      preserveAspectRatio="none"
      pointerEvents="none"
      aria-label="Model-produced segmentation mask"
    />
  );
}

export function SegmentationControls({
  evidence,
  declaredComparison = false,
  selected,
  onSelect,
}: {
  evidence: SegmentationEvidence;
  declaredComparison?: boolean;
  selected: number | null;
  onSelect: (index: number | null) => void;
}) {
  return (
    <fieldset className="segmentation-controls">
      <legend>Experimental segmentation</legend>
      <p>
        Class-agnostic regions may miss plants or include other objects. Original ranking retained.
      </p>
      {evidence.regions.length ? (
        <label>
          Mask overlay
          <select
            aria-label="Mask overlay"
            value={selected ?? ""}
            onChange={(event) =>
              onSelect(event.target.value === "" ? null : Number(event.target.value))
            }
          >
            <option value="">Original image</option>
            {evidence.regions.map((region, index) => (
              <option key={region.id} value={index}>
                Region {index + 1}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p>
          {evidence.status === "failed" ? "Proposal stage failed." : "No regions retained."}{" "}
          Baseline available.
        </p>
      )}
      {selected !== null && evidence.regions[selected] && (
        <div>
          <p>
            Mask quality is separate from species ranking; neither is identification confidence.
          </p>
          <p>
            Predicted mask IoU: {evidence.regions[selected].mask_quality.predicted_iou.toFixed(3)}
            {"; "}
            stability: {evidence.regions[selected].mask_quality.stability_score.toFixed(3)}
          </p>
          <ul>
            {Object.entries(evidence.regions[selected].views).map(([view, score]) => (
              <li key={view}>
                {view}: {watchlistHint(score, declaredComparison, names)}; top watchlist comparison:{" "}
                {score.best_species} · relative margin {score.margin.toFixed(3)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </fieldset>
  );
}
