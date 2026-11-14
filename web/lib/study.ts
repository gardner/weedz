/** A discovery study's definition, its versions and the screening terms it names. */

type Named = { rationale: string; screened: boolean };
export type Limit = { value: number; note: string };
export type StudyDefinition = {
  status: "provisional" | "agreed";
  question: string;
  partner: string;
  people: { role: string; name: string }[];
  regions: (Named & { name: string })[];
  period_start: string | null;
  period_end: string | null;
  period_rationale: string;
  watchlist: (Named & { species: string })[];
  lookalikes: (Named & { taxon: string })[];
  source_collection: string;
  subject_selection: string;
  review_budget: { hours: number | null; photos: number | null; note: string };
  reference_records: { name: string; note: string }[];
  limits: Record<string, Limit>;
};
type BudgetUse = { budget: number | null; used: number; lower_bound: boolean; state: string };
export type Study = {
  id: string;
  version: number;
  author: string;
  created_at: string;
  change_note: string;
  definition: StudyDefinition;
  open_decisions: string[];
  differences: string[];
  budget_use?: { hours: BudgetUse; photos: BudgetUse; note: string };
};
export type LimitTerms = { measure: string; direction: string; unit: string };
export type StudyTerms = {
  regions: string[];
  species: Record<string, string>;
  lookalikes: { name: string; confusable_with: string }[];
  limits: Record<string, LimitTerms>;
};

export const EMPTY: StudyDefinition = {
  status: "provisional",
  question: "",
  partner: "",
  people: [],
  regions: [],
  period_start: null,
  period_end: null,
  period_rationale: "",
  watchlist: [],
  lookalikes: [],
  source_collection: "",
  subject_selection: "",
  review_budget: { hours: null, photos: null, note: "" },
  reference_records: [],
  limits: {},
};

/** "Key: value" lines, one per item; null if a line has no key or no value. */
export function parseLines(text: string, needsValue = true): [string, string][] | null {
  const pairs: [string, string][] = [];
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const at = line.indexOf(":");
    const key = (at < 0 ? line : line.slice(0, at)).trim();
    const value = at < 0 ? "" : line.slice(at + 1).trim();
    if (!key || (needsValue && !value)) return null;
    pairs.push([key, value]);
  }
  return pairs;
}

export function toLines(pairs: [string, string][]): string {
  return pairs.map(([key, value]) => (value ? `${key}: ${value}` : key)).join("\n");
}

export function limitText(terms: LimitTerms, limit?: Limit): string {
  if (!limit) return `${terms.measure}: not yet agreed`;
  return `${terms.measure}: ${terms.direction} ${limit.value} ${terms.unit}`;
}

export function budgetText(use: BudgetUse, unit: string): string {
  const used = `${use.lower_bound ? "at least " : ""}${use.used} ${unit} used so far`;
  return use.budget === null
    ? `${used} · no budget set`
    : `${used} of ${use.budget} ${unit} (${use.state})`;
}

type Pick = { on: boolean; why: string };
export type Draft = {
  status: StudyDefinition["status"];
  question: string;
  partner: string;
  people: string;
  regions: Record<string, Pick>;
  otherRegions: string;
  periodStart: string;
  periodEnd: string;
  periodWhy: string;
  species: Record<string, Pick>;
  otherSpecies: string;
  lookalikes: Record<string, string>;
  otherLookalikes: string;
  source: string;
  selection: string;
  hours: string;
  photos: string;
  budgetNote: string;
  references: string;
  limits: Record<string, { value: string; note: string }>;
};

function picks(names: string[], chosen: (Named & { key: string })[]): Record<string, Pick> {
  return Object.fromEntries(
    names.map((name) => {
      const found = chosen.find((item) => item.key === name && item.screened);
      return [name, { on: Boolean(found), why: found?.rationale ?? "" }];
    }),
  );
}

function unscreened(items: (Named & { key: string })[]): string {
  return toLines(items.filter((item) => !item.screened).map((item) => [item.key, item.rationale]));
}

export function toDraft(study: StudyDefinition, terms: StudyTerms): Draft {
  const regions = study.regions.map((item) => ({ ...item, key: item.name }));
  const species = study.watchlist.map((item) => ({ ...item, key: item.species }));
  const lookalikes = study.lookalikes.map((item) => ({ ...item, key: item.taxon }));
  const number = (value: number | null) => (value === null ? "" : String(value));
  return {
    status: study.status,
    question: study.question,
    partner: study.partner,
    people: toLines(study.people.map((person) => [person.role, person.name])),
    regions: picks(terms.regions, regions),
    otherRegions: unscreened(regions),
    periodStart: study.period_start ?? "",
    periodEnd: study.period_end ?? "",
    periodWhy: study.period_rationale,
    species: picks(Object.keys(terms.species), species),
    otherSpecies: unscreened(species),
    lookalikes: Object.fromEntries(
      terms.lookalikes.map(({ name }) => [
        name,
        lookalikes.find((item) => item.key === name && item.screened)?.rationale ?? "",
      ]),
    ),
    otherLookalikes: unscreened(lookalikes),
    source: study.source_collection,
    selection: study.subject_selection,
    hours: number(study.review_budget.hours),
    photos: number(study.review_budget.photos),
    budgetNote: study.review_budget.note,
    references: toLines(study.reference_records.map((item) => [item.name, item.note])),
    limits: Object.fromEntries(
      Object.keys(terms.limits).map((key) => [
        key,
        { value: number(study.limits[key]?.value ?? null), note: study.limits[key]?.note ?? "" },
      ]),
    ),
  };
}

function chosen(picked: Record<string, Pick>, others: [string, string][]) {
  return [
    ...Object.entries(picked)
      .filter(([, pick]) => pick.on)
      .map(([name, pick]) => [name, pick.why.trim(), true] as const),
    ...others.map(([name, why]) => [name, why, false] as const),
  ];
}

/** The definition a draft describes, or why it cannot be saved yet. */
export function fromDraft(draft: Draft): StudyDefinition | string {
  const people = parseLines(draft.people);
  if (!people) return "Responsible people: Write each line as Role: Name.";
  const otherRegions = parseLines(draft.otherRegions, false);
  const otherSpecies = parseLines(draft.otherSpecies, false);
  const otherLookalikes = parseLines(draft.otherLookalikes, false);
  const references = parseLines(draft.references, false);
  if (!otherRegions || !otherSpecies || !otherLookalikes || !references) {
    return "Each line needs a name before any colon.";
  }
  const number = (text: string) => (text.trim() === "" ? null : Number(text));
  const limits: Record<string, Limit> = {};
  for (const [key, limit] of Object.entries(draft.limits)) {
    if (limit.value.trim() === "") continue;
    limits[key] = { value: Number(limit.value), note: limit.note.trim() };
  }
  return {
    status: draft.status,
    question: draft.question.trim(),
    partner: draft.partner.trim(),
    people: people.map(([role, name]) => ({ role, name })),
    regions: chosen(draft.regions, otherRegions).map(([name, rationale, screened]) => ({
      name,
      rationale,
      screened,
    })),
    period_start: draft.periodStart || null,
    period_end: draft.periodEnd || null,
    period_rationale: draft.periodWhy.trim(),
    watchlist: chosen(draft.species, otherSpecies).map(([species, rationale, screened]) => ({
      species,
      rationale,
      screened,
    })),
    lookalikes: [
      ...Object.entries(draft.lookalikes)
        .filter(([, why]) => why.trim())
        .map(([taxon, why]) => ({ taxon, rationale: why.trim(), screened: true })),
      ...otherLookalikes.map(([taxon, rationale]) => ({ taxon, rationale, screened: false })),
    ],
    source_collection: draft.source.trim(),
    subject_selection: draft.selection.trim(),
    review_budget: {
      hours: number(draft.hours),
      photos: number(draft.photos),
      note: draft.budgetNote.trim(),
    },
    reference_records: references.map(([name, note]) => ({ name, note })),
    limits,
  };
}
