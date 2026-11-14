// A source suitability summary as GET /runs/{id}/suitability returns it, for browser checks.
const tally = (photos, visits, ungrouped) => ({
  photos,
  site_visits: visits,
  ungrouped_photos: ungrouped,
});

export const suitability = {
  schema: 1,
  run_id: "run",
  meaning:
    "What this run's incidental photos can and cannot support, before review. A photo, area, period or year that was not collected, screened, compared or reviewed is unassessed: it is not evidence that no weed is there.",
  study: null,
  scope: {
    run_status: "completed",
    incidental: tally(2, 1, 1),
    other_photos: { reference: 1 },
    regions: { Nelson: { requested: 2, photos: 2 }, Tasman: { requested: 2, photos: 0 } },
    gaps: ["Tasman returned 0 of 2 requested photos; the rest of its coverage is unassessed"],
  },
  dates: {
    corpus: { sampling: "recent", by_year: { 2024: 2 }, by_season: { DJF: 2 } },
    earliest: "2024-12-30",
    latest: "2024-12-31",
    query_period: { start: null, end: "2024-12-31" },
    study_period: null,
    outside_study_period: null,
    undated: tally(0, 0, 0),
    imprecise: tally(0, 0, 0),
    years_without_photos: null,
    seasons_without_photos: ["MAM", "JJA", "SON"],
    notes: [
      "Recent sampling takes the newest photos first, so dates before 2024-12-30 were not sampled; they are unassessed",
    ],
  },
  locations: {
    search_areas: { searchable: 1, site_context_precision: 1, accuracy_unknown: 1 },
    not_searchable: {
      obscured: { reason: "Location obscured by the source", ...tally(0, 0, 0) },
      missing: { reason: "No location supplied; no search area", ...tally(0, 0, 0) },
      accuracy_unknown: {
        reason: "Location accuracy not supplied; the search radius cannot be stated",
        ...tally(1, 0, 1),
      },
    },
    accuracy_m: {
      reported: 1,
      not_reported: 1,
      min: 10,
      median: 10,
      max: 10,
      bands: { "up to 20 m": 1, "20 to 100 m": 0, "100 to 1,000 m": 0, "over 1,000 m": 0 },
    },
  },
  permitted_uses: {
    photo_licences: { "cc-by": 1, "cc-by-nc": 1 },
    observation_licences: { "cc-by": 2 },
    non_commercial_only: 1,
    images: { include: 2, link: 0 },
    image_link_reasons: {},
    locations: {
      shared: 1,
      withheld: { "Withheld: the location's accuracy was not supplied": 1 },
      none_supplied: 0,
    },
  },
  missing: { source: 0, date: 0, location: 1, upload_date: 0 },
  independence: {
    rule: "same observer and observed date",
    incidental_photos: 2,
    independent_site_visits: 1,
    ungrouped_photos: 1,
    observers: 2,
    observer_days: 2,
  },
  screening: {
    screened: tally(2, 1, 1),
    not_screened: tally(0, 0, 0),
    pixel_coverage: { complete: 0, thinned: 0, not_recorded: 2 },
    featureless_windows: { photos_with: 0, not_recorded: 2 },
    visible_vegetation:
      "Not measured: no step estimates how much vegetation each photo shows. Featureless windows and pixel coverage say only what the screening could see",
    original_subjects: { "Blackbird (Turdus merula)": 2 },
    reviewed: tally(0, 0, 0),
    unassessed: tally(2, 1, 1),
  },
  reference_comparison: {
    snapshot: null,
    not_queried_species: ["Clematis vitalba", "Cortaderia selloana", "Ulex europaeus"],
    compared: tally(0, 0, 0),
    not_compared: { "No reference snapshot to compare against": tally(2, 1, 1) },
  },
  cannot_support: [
    {
      key: "field_search",
      conclusion: "A field search lead",
      because: "No search area: the location is obscured, missing or of unknown accuracy",
      photos: tally(1, 0, 1),
    },
    {
      key: "study_period",
      conclusion: "A conclusion about the study period",
      because: "No study period is recorded, so photos are not checked against one",
      photos: null,
    },
    {
      key: "screening",
      conclusion: "Any screening suggestion",
      because: "Not screened yet",
      photos: tally(0, 0, 0),
    },
  ],
};
