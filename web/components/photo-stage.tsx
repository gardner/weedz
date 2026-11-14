"use client";

import Image from "next/image";
import { type PointerEvent, type ReactNode, useRef } from "react";
import { hasImage, noImageReason } from "../lib/device-reports";
import { findingName } from "../lib/findings";
import { imageUrl, names, type Photo } from "../lib/types";

type Point = [number, number];
const clamp = (value: number, max: number) => Math.min(Math.max(Math.round(value), 0), max);

/**
 * The source photo with the model's search window, recorded finding boxes and, while
 * recording a finding, a box drawn by dragging. Drawing is a shortcut: the finding form
 * takes the same box as typed pixel edges.
 */
export default function PhotoStage({
  photo,
  runId,
  windowVisible,
  drawing,
  draft,
  onDraw,
}: {
  photo: Photo;
  runId: string;
  windowVisible: boolean;
  drawing: boolean;
  draft: number[] | null;
  onDraw: (box: number[]) => void;
}) {
  const { scores } = photo;
  const svg = useRef<SVGSVGElement>(null);
  const start = useRef<Point | null>(null);
  const width = scores.width ?? 0;
  const height = scores.height ?? 0;
  const stroke = Math.max(width / 260, 2);

  function imagePoint(event: PointerEvent): Point | null {
    const matrix = svg.current?.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [clamp(point.x, width), clamp(point.y, height)];
  }

  function drag(event: PointerEvent) {
    const end = imagePoint(event);
    if (!start.current || !end) return;
    const [[x1, y1], [x2, y2]] = [start.current, end];
    if (x1 === x2 || y1 === y2) return;
    onDraw([Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2)]);
  }

  const endDrag = () => {
    start.current = null;
  };

  const caption =
    photo.cohort === "device"
      ? hasImage(photo)
        ? "Device report · crop approved and sent from a phone"
        : "Device report · no crop to show"
      : photo.cohort === "lookalike"
        ? `Lookalike photo · ${photo.lookalike_taxon}, resembles ${names[photo.lookalike_of ?? ""] ?? photo.lookalike_of}`
        : photo.cohort === "reference"
          ? "Reference photo · kept outside discovery results"
          : "Animal-subject photo · background plants unlabelled";
  if (!hasImage(photo)) {
    return (
      <div className="image-stage">
        <p className="no-image">{noImageReason(photo)}</p>
        <span className="image-caption">{caption}</span>
      </div>
    );
  }
  return (
    <div className="image-stage">
      {width && height ? (
        <svg
          ref={svg}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Source photo of ${photo.original_common_name || photo.original_taxon}; highlighted search window`}
          className={drawing ? "drawing" : undefined}
          onPointerDown={(event) => {
            if (!drawing) return;
            event.currentTarget.setPointerCapture(event.pointerId);
            start.current = imagePoint(event);
          }}
          onPointerMove={drag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <title>Original photo with an optional model search window</title>
          <image href={imageUrl(runId, photo.id)} width={width} height={height} />
          {windowVisible && scores.box && (
            <Box box={scores.box} className="search-window" stroke={stroke} dash="12 6" />
          )}
          {(photo.findings ?? []).map(
            (finding) =>
              finding.box && (
                <Box key={finding.id} box={finding.box} className="finding-box" stroke={stroke}>
                  <title>{`${findingName(finding)}, recorded by ${finding.reviewer}`}</title>
                </Box>
              ),
          )}
          {draft && <Box box={draft} className="draft-box" stroke={stroke * 1.5} />}
        </svg>
      ) : (
        <Image
          src={imageUrl(runId, photo.id)}
          alt={`Original observation of ${photo.original_taxon}`}
          width={1024}
          height={1024}
          unoptimized
        />
      )}
      <span className="image-caption">{caption}</span>
    </div>
  );
}

function Box({
  box: [x1, y1, x2, y2],
  className,
  stroke,
  dash,
  children,
}: {
  box: number[];
  className: string;
  stroke: number;
  dash?: string;
  children?: ReactNode;
}) {
  return (
    <rect
      className={className}
      x={x1}
      y={y1}
      width={x2 - x1}
      height={y2 - y1}
      strokeWidth={stroke}
      strokeDasharray={dash}
    >
      {children}
    </rect>
  );
}

/** A queue row's thumbnail; a device report without image consent has none to request. */
export function Thumbnail({ photo, runId }: { photo: Photo; runId: string }) {
  if (!hasImage(photo)) return <span className="no-thumbnail">No image</span>;
  return (
    <Image
      src={imageUrl(runId, photo.id)}
      alt={photo.original_common_name || photo.original_taxon}
      loading="lazy"
      width={68}
      height={74}
      unoptimized
    />
  );
}
