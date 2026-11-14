"use client";

import { useEffect, useState } from "react";
import { type Photo, type ReviewEvent, request, statusLabels } from "../lib/types";

/** Stored times are UTC; show them in the reviewer's own time zone and locale. */
const decidedAt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** Attributed decision history for one photo. The parent remounts it after each decision. */
export default function ReviewHistory({ runId, photo }: { runId: string; photo: Photo }) {
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    request<ReviewEvent[]>(`runs/${runId}/photos/${photo.id}/reviews`)
      .then((result) => {
        if (current) setEvents(result);
      })
      .catch(() => {
        if (current) setError("Review history is unavailable.");
      });
    return () => {
      current = false;
    };
  }, [runId, photo.id]);

  return (
    <section className="review-history" aria-label="Review history">
      <h3>Decision history</h3>
      {error && <p>{error}</p>}
      {!error && !events.length && <p>No decisions yet.</p>}
      <ol>
        {events.map((event) => (
          <li key={event.id}>
            <strong>{event.reviewer || "Reviewer not recorded"}</strong>{" "}
            <span>{statusLabels[event.status] ?? event.status}</span>{" "}
            <time dateTime={event.created_at}>{decidedAt.format(new Date(event.created_at))}</time>
            {event.note && <p>{event.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
