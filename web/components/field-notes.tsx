import { names } from "../lib/types";

/** Reviewer guidance beside the evidence; scores are shown with their meaning in the evidence. */
export default function FieldNotes() {
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
      <div className="notes-rule" />
      <p className="location-note">
        A photo location is an observation location. It may be obscured, approximate or distant from
        the plant.
      </p>
    </aside>
  );
}
