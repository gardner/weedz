# Weedz — Product Requirements Document

Status: Draft for product review. Date: 13 November 2026.

## Product summary

Weedz helps conservation and biosecurity teams discover invasive plants
incidentally visible in existing photographs. A photo taken to record a bird,
insect, animal, or landscape may contain a weed that nobody recorded. Weedz
surfaces that overlooked evidence for specialist review and useful follow-up.

For example, a butterfly observation may show an invasive vine on the fence
behind it. The product should preserve the butterfly observation and identify
the vine as a separate candidate finding, with its own evidence and review.

The proposed first release is a bounded retrospective study of historical
New Zealand imagery. It should establish whether incidental plant discoveries
are reliable, informative, and worth the effort of reviewing them. The existing
research prototype does not demonstrate this capability or establish field readiness.

## Problem and opportunity

Existing photographs may contain ecological evidence beyond their original
subject. Searching only their original species labels leaves that evidence
undiscovered. Inspecting every photograph manually is expensive, and large
collections contain repeated views, poor images, and many genuine negatives.

Conservation teams need credible leads about overlooked weeds, particularly
unusual occurrences and evidence of earlier presence. A large number of plausible
suggestions has little value if it overwhelms reviewers or cannot guide follow-up.
A photograph's age and approximate location also limit what can be concluded
about a plant visible in the background.

Weedz should complement existing biodiversity records and weed alert services.
Its distinct contribution is discovering visual evidence that the original
record did not identify. A finding absent from a particular reference collection
is not automatically the first occurrence of that species in the area.

These are product hypotheses. The pilot must establish the yield of useful
incidental discoveries, the effort required to verify them, and their value to
people making biosecurity and conservation decisions.

## Users and their jobs

| User | Job to accomplish | What a good outcome looks like |
| --- | --- | --- |
| Biosecurity officer or conservation coordinator | Find useful evidence of overlooked infestations or unexpected occurrences | A small, prioritised set of credible leads with clear evidence and location limits |
| Ecologist or weed identification specialist | Verify incidental plants, including confusing native or cultivated lookalikes | The original photo, relevant detail, and context needed to confirm, correct, reject, or defer a finding |
| Imagery reviewer | Work through candidate discoveries efficiently | Clear review progress, saved decisions, and a way to add missed plants and request specialist help |
| Collection steward | Assemble eligible imagery and reliable reviewed examples | Source history, accountable corrections, reuse eligibility, and visible coverage gaps |
| Field surveyor | Follow up a credible lead where a visit is useful | A concise evidence package that distinguishes an approximate search area from a verified plant location |

A small pilot team may fill several roles. Decisions about identification,
location usefulness, novelty, and follow-up value may need different expertise.

## Goals

1. Find invasive plants overlooked in photographs whose original subject or label
   does not identify the target weed.
2. Produce verified leads at a review effort the partner can sustain.
3. Distinguish evidence newly found in a photo from a genuinely new locality or
   earlier documented presence.
4. Make uncertainty about identity, image date, location, and current presence
   understandable when a reviewer or coordinator makes a decision.
5. Produce evidence packages useful for specialist assessment and field follow-up.
6. Build reliable reference examples across habitats, seasons, viewpoints, and
   sources while preserving the original observations and their owners' attribution.

## Initial release scope

The proposed pilot uses an accessible, eligible historical collection from one
NZ region and a small weed watchlist selected with local specialists. Nelson/Tasman
and old man's beard are provisional choices from the research brief. Other
candidates include Chilean rhubarb, pampas, and wilding conifers; the final list
must reflect visual identifiability, important lookalikes, and management value.
Gorse remains a possible target rather than an assumed first priority.

The initial collection should include photographs taken for other purposes,
with several independent locations or encounters. Candidate sources include
wildlife camera imagery, community observations, roadside photographs, and
landscapes. Existing animal labels and descriptions of frames as "empty" do not
establish whether weeds are visible. Plants already identified as the original
subject can be useful reference examples, but do not demonstrate incidental discovery.

Begin with a bounded collection and a declared review budget. Increase the volume
only when discovery yield and review effort support doing so. Acquiring new or
restricted public-agency footage is not a prerequisite for the pilot.

### Required for the pilot

- Define a watchlist, region, historical period, eligible photo collection, and
  the discovery question the partner wants answered.
- Retain the original subject, source, relevant dates, attribution, and location limits.
- Inspect likely secondary plants within the full original photograph and its context.
- Confirm, correct, reject, or defer an identification; add an overlooked candidate.
- Distinguish repeated photographic evidence from independent candidate occurrences.
- Assess identity, location usefulness, historical relevance, and novelty separately.
- Compare reviewed findings with an agreed reference record collection without
  treating missing records as proof of novelty or absence.
- Produce a prioritised evidence package with appropriate follow-up recommendations.
- Curate accepted and disputed examples with accountable review decisions.

### Later opportunities

Ongoing monitoring of newly available photos, additional regions and species,
vegetation changes over time, related aerial evidence, and field-result feedback
may follow a successful retrospective study. Potential handoffs to existing weed
alert services are future opportunities; no direct integration is assumed.

### Outside the first release

Universal weed identification, exact ground mapping from arbitrary photographs,
claims that an unreviewed area is weed-free, automatic external alerts or new
third-party observations, treatment execution, and an open-data advocacy campaign
are outside the pilot. Aerial patch mapping remains a possible supporting product
rather than the first release's primary workflow.

## Core user journeys

### 1. Define a discovery study

A coordinator chooses the watchlist, area, historical period, and photo collection.
They see the collection's coverage, original subjects, dates, reuse restrictions,
and location limitations. They agree on what makes a lead useful, how much review
is affordable, and which existing records will be used for comparison.

### 2. Inspect incidental plants

A reviewer sees the proposed plant in the full photograph, with the relevant
visual detail highlighted. They can inspect context, consider lookalikes, correct
an identification, add a missed plant, reject an artefact, or request specialist
review. The original photo's subject remains separate from the candidate weed.

Work can be resumed. Uncertain or inconclusive findings remain explicit rather
than being forced into a positive or negative decision. Reviewers can also inspect
photographs without proposed findings to check for missed plants.

### 3. Establish the value of a finding

A specialist reviews the identification evidence. A coordinator assesses whether
its date and location support a useful lead, whether it repeats other evidence,
and whether it adds information beyond the agreed reference records. A credible
visual finding outside the expected range remains reviewable.

The outcome may be an overlooked plant in a known locality, an earlier photograph
than the available records, a potentially new locality, or evidence too uncertain
for follow-up. Each conclusion states what is known and what still needs checking.

### 4. Prepare a follow-up package

The team selects leads worth investigating and records why. Each package includes
original source links, the full photograph and relevant detail where sharing is
permitted, the candidate species, capture date, location quality, review decisions,
and the evidence behind any novelty claim. A historical photo does not assert
that the plant remains present today. Field staff receive a search area and its
limits rather than unsupported plant coordinates.

### 5. Improve the reference collection

A steward reviews accepted examples, difficult negatives, unresolved cases, and
repeated encounters. Specialists record corrections and supporting evidence while
preserving the original photo and observation. The team can identify gaps in
species, growth stages, habitats, viewing angles, and source collections.

## Product requirements

All requirements are proposed pilot requirements. Acceptance criteria describe
user-observable outcomes and do not prescribe implementation.

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| P01 | Define a bounded discovery study | Users can identify the watchlist, region, period, source collection, original-subject selection, review budget, and responsible people |
| P02 | Establish source suitability | Users can understand coverage, dates, visibility, permitted uses, missing information, and which photographs cannot support the requested conclusions |
| P03 | Find secondary subjects | A target plant can become a candidate when the photo was labelled with a different subject; the original subject is retained and is not reused as the weed identification |
| P04 | Present reviewable visual evidence | Reviewers can inspect the candidate's detail and full-photo context, compare important lookalikes, and understand uncertainty |
| P05 | Keep independent judgments separate | Identity, review status, location usefulness, historical relevance, and novelty can remain independently confirmed, disputed, or unresolved |
| P06 | Correct findings and find misses | Reviewers can change an identification or visible extent, reject a candidate, add a missed plant, or request specialist assessment with a reason |
| P07 | Preserve accountable review | Users can resume work, understand disagreements, see the current decision and reviewer, and inspect the reasons for material changes |
| P08 | Avoid inflated discovery counts | Repeated frames and photos of the same encounter are presented as related evidence rather than automatically counted as independent infestations |
| P09 | Communicate location and date limits | Capture date is distinguished from upload or discovery date; camera/observation location is distinguished from plant location; uncertain dates and locations remain explicit |
| P10 | Make novelty claims proportionate | Users can distinguish a new finding in a photograph, a finding absent from the chosen reference records, an earlier available image, and a locality independently verified as new |
| P11 | Retain unusual but credible leads | Known distributions help reviewers prioritise work but do not automatically exclude visually credible out-of-range candidates |
| P12 | Produce a useful follow-up package | Permitted evidence, attribution, review state, location/date limits, comparison basis, and the reason for follow-up accompany shared findings |
| P13 | Curate reliable reference evidence | Stewards can distinguish originals from accepted corrections, disputed or unsuitable examples, and examples eligible for a particular use |
| P14 | Show assessed and unassessed coverage | Users can see which parts of the study were assessed and reviewed; a missing suggestion or record is not presented as verified weed absence |
| P15 | Respect source and contributor restrictions | Sharing and reuse preserve attribution, source permissions, and location privacy; no automatic publication of a new observation on someone else's behalf is included |
| P16 | Make review accessible | Core review actions are keyboard-accessible, status is not communicated by colour alone, and users understand decisions without specialist software knowledge |

## Product behavior in difficult cases

| Situation | Expected experience |
| --- | --- |
| The original record is about an animal or labels a frame as empty | Treat the original label as context, not evidence that vegetation is absent |
| A plant is too small, blurred, obscured, or lacks diagnostic features | Mark identity unresolved and explain what additional evidence is needed |
| A native or cultivated lookalike is plausible | Keep that alternative visible and refer unresolved cases for appropriate specialist review |
| The source location is obscured or the plant is distant from the photographer | Preserve the uncertainty and avoid an invented precise plant location |
| A photograph predates the available occurrence records | Describe it as earlier photographic evidence relative to those records, not proof of introduction date |
| The weed is outside its recorded range | Keep credible evidence available for specialist review rather than discard it for being unexpected |
| Many images repeat the same camera view or plant | Group them as related evidence so review effort and discovery counts are not misleading |
| No comparison records are available | Mark novelty unassessed; do not claim a new locality |
| A historical finding may no longer be present | Separate historical evidence from current status and make any follow-up need clear |
| A source or external service is unavailable | Continue with eligible available evidence and show the affected coverage |

## Success measures

The primary outcome is **verified, useful incidental discoveries at a sustainable
review effort**. The retrospective pilot must establish value beyond finding
plants already identified in their original records.

| Measure | How it is assessed | Pilot success condition |
| --- | --- | --- |
| Useful incidental yield | Count independently reviewed, deduplicated findings whose target was not identified in the original record | Produces leads the partner considers worth investigation, beyond a study consisting only of known target observations |
| Reviewer effort per useful finding | Include all triage, specialist review, false alarms, and duplicate handling | Fits the partner's agreed review capacity and improves on comparable manual searching |
| Missed visible targets | Independently review a representative sample, including photos with no proposed findings | Meets watchlist- and condition-specific limits agreed before the pilot |
| Novel or earlier evidence | Assess findings against the declared reference records, preserving uncertainty about their completeness | Supports defensible claims of added information rather than unsupported first-occurrence claims |
| False-alarm workload | Measure rejected and inconclusive leads and the time they consume | Does not overwhelm review capacity or erase discovery value |
| Follow-up usefulness | Have intended users assess whether evidence and location quality support an actual next step | Supports specialist assessment, a meaningful site visit, or a justified historical record update |
| Evidence and review completeness | Inspect shared leads for source, attribution, dates, uncertainty, and decisions | Every lead communicates the evidence and limits behind its conclusion |
| Coverage and review usability | Observe intended users completing the study and identify poorly served conditions | Users can complete the core journey and explain which evidence remains unassessed |

Rare targets may produce many more false alarms than useful leads even when
individual examples look convincing. Overall photo-classification accuracy alone
is not a pilot success measure. Report independent encounters and sites alongside
photo counts so repeated images do not inflate results.

Numeric limits for useful yield, review effort, missed visible targets, turnaround,
and false-alarm workload must be agreed before the pilot. They depend on species,
visibility, source coverage, and operational value. These remain open launch
criteria rather than invented universal performance promises.

## Pilot and release readiness

1. **Agree on the question:** confirm the partner, region, watchlist, intended
   follow-up, reference records, and the value of new or earlier evidence.
2. **Agree on the study:** choose an accessible eligible historical collection,
   define independent encounters and review responsibilities, and set success limits.
3. **Run a bounded retrospective pilot:** inspect candidates and missed examples,
   adjudicate identity, and assess location, historical relevance, and novelty.
4. **Assess real value:** measure deduplicated useful findings and complete review
   effort; separate visual identification from the value of a local occurrence lead.
5. **Decide whether to expand:** increase sources, volume, species, or monitoring
   frequency only when the evidence supports a useful repeatable service.

The current prototype and labelled species examples are supporting research.
They do not establish that useful background discoveries can be made in a new
collection. Access to restricted road-survey footage or a new public-data release
is not a release dependency.

## Assumptions and open product decisions

- Which team would act on the first incidental discovery, and what would it do?
- Is Nelson/Tasman the right pilot area, and which weeds are identifiable and valuable there?
- Which eligible image collection offers enough visible vegetation, dates, and
  actionable location information for a bounded study?
- What counts as independent evidence when photographs repeat a camera site or encounter?
- Which reference records establish the comparison, and how complete are they?
- What additional evidence is required before claiming a new locality or earlier presence?
- Who can resolve botanical lookalikes, cultivated-versus-wild context, and disputed findings?
- How much review effort per useful lead can the partner sustain?
- Which historical discoveries would still justify present-day follow-up?
- What uses of source photos and derived evidence are permitted for the pilot and later service?
- What sharing process would be appropriate for the source community and existing weed services?
- What commercial or funding arrangement would make repeated use sustainable?

These decisions refine pilot scope and launch criteria. Model selection, data
processing, infrastructure, and other implementation choices are outside this PRD.
