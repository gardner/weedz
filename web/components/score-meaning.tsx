import { marginWords, meaningLabel, modelName, type ScoreMeaning } from "../lib/score-meaning";
import { names, type Photo } from "../lib/types";

/** The run-wide reminder above the queue, naming the model that actually scored the run. */
export function ScreeningNote({ meaning }: { meaning?: ScoreMeaning }) {
  return (
    <div className="screening-note">
      <span className="note-icon" aria-hidden="true">
        i
      </span>
      <p>
        <strong>Screening, awaiting expert review.</strong> {modelName(meaning)} ranks full images
        and overlapping windows. Scores are relative margins, not probabilities, and no detection
        threshold has been chosen. Location novelty and weed boundaries have not been established.
      </p>
    </div>
  );
}

/** The declared threshold and abstention rule, or that none has been chosen. */
function OperatingPoint({ meaning }: { meaning: ScoreMeaning }) {
  const { operating_point: point, abstention } = meaning;
  if (point === null && abstention === null) {
    return (
      <p>No threshold or abstention rule has been chosen. {meaning.choosing_an_operating_point}</p>
    );
  }
  return (
    <>
      <p>Operating point: {point ?? "none chosen."}</p>
      <p>Abstention rule: {abstention ?? "none chosen."}</p>
    </>
  );
}

function MeaningDetails({ meaning }: { meaning: ScoreMeaning }) {
  return (
    <details className="score-meaning">
      <summary>What this score means</summary>
      <p>{meaning.score}</p>
      <p>{meaning.use}</p>
      <h4>What it does not mean</h4>
      <ul>
        {meaning.not_meaning.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <h4>Operating point</h4>
      <OperatingPoint meaning={meaning} />
      <h4>Evidence</h4>
      {meaning.evidence.length ? (
        <ul>
          {meaning.evidence.map((item) => (
            <li key={item.key}>
              {item.finding}
              <small>
                {item.labels} · {item.source}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p>No measured evidence is declared for this screening configuration.</p>
      )}
      <p>{meaning.run_evidence}</p>
    </details>
  );
}

/** Each species' margin in words, with the declared meaning of the run's scores. */
export function ScorePanel({ photo, meaning }: { photo: Photo; meaning?: ScoreMeaning }) {
  const rows = photo.scores.species ?? [];
  return (
    <section className="score-panel" aria-labelledby="score-heading">
      <h3 id="score-heading">Ranking score</h3>
      <p className="score-label">{meaningLabel(meaning)}</p>
      {rows.length ? (
        <ul className="score-margins">
          {rows.map((row) => (
            <li key={row.name}>
              <span>
                {names[row.name] ?? row.name}
                {row.name === photo.scores.best_species && " (top watchlist comparison)"}
              </span>
              <b>{marginWords(row.margin)}</b>
            </li>
          ))}
        </ul>
      ) : (
        <p>Not screened yet.</p>
      )}
      {meaning && <MeaningDetails meaning={meaning} />}
    </section>
  );
}
