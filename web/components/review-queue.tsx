import { useEffect, useRef } from "react";
import { auditedBy, VIEWS, type View } from "../lib/queue";
import { needsSpecialist } from "../lib/referrals";
import { names, type Photo, siteVisitNote } from "../lib/types";
import { Thumbnail } from "./photo-stage";

type Props = {
  photos: Photo[];
  activeId?: string;
  runId: string;
  cohort: View;
  region: string;
  review: string;
  reviewer: string;
  held: number;
  loading: boolean;
  acquiring: boolean;
  onCohortChange: (view: View) => void;
  onRegionChange: (region: string) => void;
  onReviewChange: (review: string) => void;
  onSelect: (id: string) => void;
};
export default function ReviewQueue({
  photos: filtered,
  activeId,
  runId,
  cohort,
  region,
  review,
  reviewer,
  held,
  loading,
  acquiring,
  onCohortChange,
  onRegionChange,
  onReviewChange,
  onSelect,
}: Props) {
  const strip = useRef<HTMLDivElement>(null);
  const queueIdentity = JSON.stringify(filtered.map((photo) => photo.id));
  useEffect(() => {
    const list = strip.current;
    if (!activeId) {
      if (list) list.scrollLeft = 0;
      return;
    }
    if (!list || queueIdentity === "[]") return;
    function revealSelected() {
      if (!list) return;
      const selected = list.querySelector<HTMLButtonElement>(".selected");
      if (!selected) return;
      const left =
        selected.getBoundingClientRect().left - list.getBoundingClientRect().left + list.scrollLeft;
      if (left < list.scrollLeft) list.scrollLeft = left;
      else if (left + selected.offsetWidth > list.scrollLeft + list.clientWidth)
        list.scrollLeft = left + selected.offsetWidth - list.clientWidth;
    }
    revealSelected();
    const observer = new ResizeObserver(revealSelected);
    observer.observe(list);
    return () => observer.disconnect();
  }, [activeId, queueIdentity]);
  const auditing = cohort === "audit";
  const specialist = cohort === "specialist";
  return (
    <section className="queue" aria-label="Photo review queue">
      <div className="queue-heading">
        <h2>
          Review queue <span>{filtered.length}</span>
        </h2>
        <p>
          {auditing
            ? "Fixed random sample · screening rank hidden"
            : `${specialist ? "Open referrals, longest waiting first" : "Highest relative similarity first"}${held ? ` · ${held} held for blind audit` : ""}`}
        </p>
      </div>
      <div className="cohort-tabs">
        {VIEWS.map(([view, label]) => (
          <button
            type="button"
            key={view}
            aria-pressed={cohort === view}
            onClick={() => onCohortChange(view)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="queue-filters">
        {cohort !== "device" && (
          <select
            aria-label="Filter region"
            value={region}
            onChange={(event) => onRegionChange(event.target.value)}
          >
            <option value="all">Both regions</option>
            <option>Nelson</option>
            <option>Tasman</option>
          </select>
        )}
        {!auditing && !specialist && (
          <select
            aria-label="Filter review status"
            value={review}
            onChange={(event) => onReviewChange(event.target.value)}
          >
            <option value="all">All decisions</option>
            <option value="unreviewed">Needs review</option>
            <option value="confirmed">Species visible</option>
            <option value="rejected">Rejected</option>
            <option value="uncertain">Uncertain</option>
          </select>
        )}
      </div>
      <div className="photo-list" ref={strip}>
        {filtered.map((photo, index) => (
          <button
            type="button"
            key={photo.id}
            className={`photo-row ${activeId === photo.id ? "selected" : ""}`}
            onClick={() => {
              onSelect(photo.id);
            }}
            aria-pressed={activeId === photo.id}
          >
            <Thumbnail photo={photo} runId={runId} />
            <span className="photo-row-body">
              <span className="row-index">
                {String(index + 1).padStart(2, "0")} / {photo.region}
              </span>
              <strong>
                {auditing
                  ? "Blind audit photo"
                  : (names[photo.scores.best_species ?? ""] ?? "Awaiting screening")}
              </strong>
              <span>{photo.original_common_name || photo.original_taxon}</span>
              <small>
                {photo.observed_on ?? "Date unknown"} ·{" "}
                {auditing
                  ? auditedBy(photo, reviewer)
                    ? "Audited"
                    : "Not yet audited"
                  : photo.review_status === "unreviewed"
                    ? "Needs review"
                    : photo.review_status}
                {!auditing && photo.disputed && " · Reviewers disagree"}
                {!auditing && needsSpecialist(photo) && " · Needs specialist"}
                {!auditing && siteVisitNote(photo) && ` · ${siteVisitNote(photo)}`}
              </small>
            </span>
          </button>
        ))}
        {!filtered.length && (
          <div className="empty-state">
            {loading
              ? "Loading local evidence…"
              : acquiring
                ? "Collecting eligible source photos…"
                : "No photos match this view."}
          </div>
        )}
      </div>
    </section>
  );
}
