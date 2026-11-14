import { dateLines, observationPoint, searchAreaBasis, searchAreaHeadline } from "../lib/limits";
import type { Photo } from "../lib/types";

const NOT_STATED = "Not stated for this photo; reload the run";

/** Capture, upload and screening dates; a photo never asserts the plant is there now. */
export function PhotoDates({ photo }: { photo: Photo }) {
  const dates = photo.limits?.dates;
  return (
    <div className="photo-dates">
      <span>Dates</span>
      <strong>
        {photo.observed_on ? `Photographed ${photo.observed_on}` : "Photo date unknown"}
      </strong>
      {dates ? (
        <>
          {dateLines(dates).map((line) => (
            <small key={line}>{line}</small>
          ))}
          <small>{dates.current_presence}.</small>
        </>
      ) : (
        <small>{NOT_STATED}</small>
      )}
    </div>
  );
}

/** Where a search could start: around the observation point, never a plant location. */
export function SearchAreaNote({ photo }: { photo: Photo }) {
  const area = photo.limits?.search_area;
  if (!area) {
    return (
      <div className="search-area">
        <span>Search area</span>
        <strong>{NOT_STATED}</strong>
      </div>
    );
  }
  const point = observationPoint(area, photo.latitude, photo.longitude);
  return (
    <div className="search-area">
      <span>Search area</span>
      <strong>{searchAreaHeadline(area)}</strong>
      {point && <small>{point}</small>}
      <small>{searchAreaBasis(area, photo.positional_accuracy_m)}</small>
    </div>
  );
}
