"use client";

import { useRef, useState } from "react";
import {
  comparisonLines,
  countsText,
  dateLines,
  locationLines,
  type Suitability,
  screeningLines,
  tallyText,
  useLines,
} from "../lib/suitability";
import { request } from "../lib/types";

type Loaded = { report: Suitability } | { error: string } | null;

function Lines({ lines }: { lines: string[] }) {
  return (
    <ul>
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

function CannotSupport({ items }: { items: Suitability["cannot_support"] }) {
  return (
    <table className="suitability-table">
      <caption>What these photos cannot support</caption>
      <thead>
        <tr>
          <th scope="col">Conclusion</th>
          <th scope="col">Photos that cannot support it</th>
          <th scope="col">Because</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.key}>
            <th scope="row">{item.conclusion}</th>
            <td>{tallyText(item.photos)}</td>
            <td>{item.because}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Report({ report }: { report: Suitability }) {
  const { scope, study } = report;
  const regions = Object.entries(scope.regions).map(
    ([name, item]) => `${name}: ${item.photos} of ${item.requested} requested`,
  );
  const sections: [string, string[]][] = [
    [
      "Scope",
      [
        `Run ${scope.run_status}. Incidental: ${tallyText(scope.incidental)}`,
        regions.join("; "),
        study
          ? `Study ${study.id}, version ${study.version}`
          : "No study linked, so no study period or regions to check against",
        ...(study?.differences ?? []),
      ],
    ],
    ["Dates", dateLines(report.dates)],
    ["Location quality", locationLines(report.locations)],
    ["Permitted uses", useLines(report.permitted_uses)],
    [
      "Missing information",
      [`Photos missing each field: ${countsText(report.missing, (n) => n.replaceAll("_", " "))}`],
    ],
    ["Independence and screening", screeningLines(report.screening, report.independence)],
    ["Original subjects", [countsText(report.screening.original_subjects)]],
    ["Comparison with known records", comparisonLines(report.reference_comparison)],
  ];
  return (
    <div className="suitability-report">
      <p>{report.meaning}</p>
      {scope.gaps.length > 0 && (
        <>
          <h2>Affected coverage</h2>
          <Lines lines={scope.gaps} />
        </>
      )}
      {sections.map(([title, lines]) => (
        <section key={title} aria-label={title}>
          <h2>{title}</h2>
          <Lines lines={lines} />
        </section>
      ))}
      <CannotSupport items={report.cannot_support} />
    </div>
  );
}

/** What the run's photos can and cannot support, fetched afresh each time it is opened. */
export default function SuitabilityPanel({ runId }: { runId: string }) {
  const [loaded, setLoaded] = useState<Loaded>(null);
  // Only the latest opening's answer is shown, whatever order the answers arrive in.
  const latest = useRef(0);

  function toggle(open: boolean) {
    if (!open || !runId) return;
    const generation = ++latest.current;
    const show = (result: Loaded) => generation === latest.current && setLoaded(result);
    setLoaded(null);
    request<Suitability>(`runs/${runId}/suitability`)
      .then((report) => show({ report }))
      .catch((failure) =>
        show({ error: failure instanceof Error ? failure.message : String(failure) }),
      );
  }

  return (
    <details className="suitability-panel" onToggle={(event) => toggle(event.currentTarget.open)}>
      <summary>
        Source suitability <span>What these photos can and cannot support</span>
      </summary>
      {!runId ? (
        <p>No run yet: start one to see what its photos cover.</p>
      ) : loaded === null ? (
        <p role="status">Loading the source suitability…</p>
      ) : "error" in loaded ? (
        <p role="alert">
          Source suitability could not be loaded: {loaded.error}. Its coverage is unknown, not
          empty.
        </p>
      ) : (
        <Report report={loaded.report} />
      )}
    </details>
  );
}
