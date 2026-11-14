import { names, type Photo } from "../lib/types";

/** Reviewer guidance beside the evidence; similarity rows are omitted in blind audits. */
export default function FieldNotes({ species }: { species?: Photo["scores"]["species"] }) {
  return (
    <aside className="field-notes">
      <span className="eyebrow">FIELD NOTES</span>
      <h3>Read the whole scene.</h3>
      <p>Original labels describe the observed animal, not every plant in the photo.</p>
      <div className="notes-rule" />
      <h4>Provisional watchlist</h4>
      {Object.entries(names).map(([scientific, common]) => (
        <div className="watch-species" key={scientific}>
          <strong>{common}</strong>
          <em>{scientific}</em>
        </div>
      ))}
      <div className="notes-rule" />
      <h4>Check the lookalikes</h4>
      <p>
        Native clematis and toetoe can resemble targets. A model ranking alone cannot resolve
        species.
      </p>
      {species && (
        <>
          <h4>Similarity comparison</h4>
          {species.map((row) => (
            <div className="score-row" key={row.name}>
              <span>{names[row.name]}</span>
              <b>{row.similarity.toFixed(3)}</b>
            </div>
          ))}
          <small>Raw cosine similarity. Ranking uses the margin against comparison labels.</small>
        </>
      )}
      <div className="notes-rule" />
      <p className="location-note">
        A photo location is an observation location. It may be obscured, approximate or distant from
        the plant.
      </p>
    </aside>
  );
}
