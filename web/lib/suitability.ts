/**
 * A run's source suitability, computed in Python (weedz.discovery.suitability): what its
 * incidental photos can and cannot support before review. Unknown stays unknown, and an
 * unassessed photo, area or year is never presented as weed-free.
 */
export type Tally = { photos: number; site_visits: number; ungrouped_photos: number };
type Period = { start: string | null; end: string | null };
type Counts = Record<string, number>;

export type Suitability = {
  run_id: string;
  meaning: string;
  study: { id: string; version: number; regions: string[]; differences: string[] } | null;
  scope: {
    run_status: string;
    incidental: Tally;
    other_photos: Counts;
    regions: Record<string, { requested: number; photos: number }>;
    gaps: string[];
  };
  dates: {
    corpus: { sampling?: string; by_year?: Counts; by_season?: Counts };
    earliest: string | null;
    latest: string | null;
    query_period: Period;
    study_period: Period | null;
    outside_study_period: Tally | null;
    study_period_unknown: Tally | null;
    undated: Tally;
    imprecise: Tally;
    years_without_photos: number[] | null;
    seasons_without_photos: string[];
    notes: string[];
  };
  locations: {
    search_areas: { searchable: number; site_context_precision: number };
    not_searchable: Record<string, Tally & { reason: string }>;
    accuracy_m: {
      reported: number;
      not_reported: number;
      min: number | null;
      median: number | null;
      max: number | null;
      bands: Counts;
    };
  };
  permitted_uses: {
    photo_licences: Counts;
    observation_licences: Counts;
    non_commercial_only: number;
    images: { include: number; link: number };
    image_link_reasons: Counts;
    locations: { shared: number; withheld: Counts; none_supplied: number };
  };
  missing: Counts;
  independence: {
    rule: string;
    independent_site_visits: number;
    ungrouped_photos: number;
    observers: number | null;
    observer_days: number | null;
  };
  screening: {
    screened: Tally;
    not_screened: Tally;
    pixel_coverage: { complete: number; thinned: number; not_recorded: number };
    featureless_windows: { photos_with: number; not_recorded: number };
    visible_vegetation: string;
    original_subjects: Counts;
    reviewed: Tally;
    unassessed: Tally;
  };
  reference_comparison: {
    snapshot: { retrieved_at: string | null; title: string | null } | null;
    not_queried_species: string[];
    compared: Tally;
    not_compared: Record<string, Tally>;
  };
  cannot_support: { key: string; conclusion: string; because: string; photos: Tally | null }[];
};

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

/** Photos with their independent site visits; "none" for no photos, "not assessed" for null. */
export function tallyText(tally: Tally | null): string {
  if (tally === null) return "Not assessed";
  if (!tally.photos) return "None";
  const visits = plural(tally.site_visits, "site visit");
  return `${plural(tally.photos, "photo")}: ${visits} + ${plural(tally.ungrouped_photos, "ungrouped photo")}`;
}

/** "name 3, other 1", or "none". */
export function countsText(counts: Counts, label: (name: string) => string = (n) => n): string {
  const parts = Object.entries(counts).map(([name, count]) => `${label(name)} ${count}`);
  return parts.join(", ") || "none";
}

function periodText(period: Period | null): string {
  if (!period) return "not recorded";
  return `${period.start ?? "open start"} to ${period.end ?? "open end"}`;
}

export function dateLines(dates: Suitability["dates"]): string[] {
  const years = dates.years_without_photos;
  return [
    `Photographed ${dates.earliest ?? "unknown"} to ${dates.latest ?? "unknown"}; query period ${periodText(dates.query_period)} (${dates.corpus.sampling ?? "unknown"} sampling); study period ${periodText(dates.study_period)}`,
    `Outside the study period: ${dates.study_period ? tallyText(dates.outside_study_period) : "not assessed"}. Cannot be placed in it: ${dates.study_period ? tallyText(dates.study_period_unknown) : "not assessed"}. Undated: ${tallyText(dates.undated)}. Dated only to a month or year: ${tallyText(dates.imprecise)}`,
    `By year: ${countsText(dates.corpus.by_year ?? {})}. By season: ${countsText(dates.corpus.by_season ?? {})}`,
    `Years with no photos: ${years === null ? "unknown (open start)" : years.join(", ") || "none"}. Seasons with no photos: ${dates.seasons_without_photos.join(", ") || "none"}`,
    ...dates.notes,
  ];
}

const metres = (value: number | null) => (value === null ? "unknown" : `${value} m`);

export function locationLines(locations: Suitability["locations"]): string[] {
  const { search_areas: areas, accuracy_m: accuracy } = locations;
  return [
    `With a search area: ${areas.searchable} photos; precise enough for aerial site context: ${areas.site_context_precision}`,
    ...Object.values(locations.not_searchable)
      .filter((item) => item.photos)
      .map((item) => `${item.reason}: ${tallyText(item)}`),
    `Reported accuracy: ${accuracy.reported} reported, ${accuracy.not_reported} not reported; min ${metres(accuracy.min)}, median ${metres(accuracy.median)}, max ${metres(accuracy.max)}`,
    `Accuracy bands: ${countsText(accuracy.bands)}`,
  ];
}

export function useLines(uses: Suitability["permitted_uses"]): string[] {
  return [
    `Photo licences: ${countsText(uses.photo_licences)}. Observation licences: ${countsText(uses.observation_licences)}`,
    `Non-commercial use only: ${uses.non_commercial_only} photos`,
    `Images that may be shared: ${uses.images.include}; link only: ${uses.images.link}`,
    ...Object.entries(uses.image_link_reasons).map(([reason, count]) => `${reason}: ${count}`),
    `Locations that may be shared: ${uses.locations.shared}; none supplied: ${uses.locations.none_supplied}`,
    ...Object.entries(uses.locations.withheld).map(([reason, count]) => `${reason}: ${count}`),
  ];
}

export function screeningLines(
  screening: Suitability["screening"],
  independence: Suitability["independence"],
): string[] {
  const { pixel_coverage: pixels, featureless_windows: featureless } = screening;
  return [
    `Independent site visits: ${independence.independent_site_visits}; ungrouped photos: ${independence.ungrouped_photos}; observers: ${independence.observers ?? "unknown"}; observer-days: ${independence.observer_days ?? "unknown"}`,
    `Screened: ${tallyText(screening.screened)}. Not screened: ${tallyText(screening.not_screened)}`,
    `Every pixel covered by tiles: yes ${pixels.complete}, thinned ${pixels.thinned}, not recorded ${pixels.not_recorded}. With featureless windows: ${featureless.photos_with}; not recorded ${featureless.not_recorded}`,
    `Visible vegetation: ${screening.visible_vegetation}`,
    `Reviewed: ${tallyText(screening.reviewed)}. Unassessed: ${tallyText(screening.unassessed)}`,
  ];
}

export function comparisonLines(comparison: Suitability["reference_comparison"]): string[] {
  const basis = comparison.snapshot
    ? `${comparison.snapshot.title ?? "Reference records"}, retrieved ${comparison.snapshot.retrieved_at?.slice(0, 10) ?? "unknown"}`
    : "No reference snapshot: novelty is unassessed";
  return [
    `Basis: ${basis}`,
    `Compared: ${tallyText(comparison.compared)}`,
    `Watchlist species the snapshot did not query: ${comparison.not_queried_species.join(", ") || "none"}`,
    ...Object.entries(comparison.not_compared).map(
      ([reason, tally]) => `Not compared, ${reason}: ${tallyText(tally)}`,
    ),
  ];
}
