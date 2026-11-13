# Weedz — Product Requirements Document

Status: Draft for product review. Date: 13 November 2026.

## Product summary

Weedz helps people responsible for land and biodiversity find likely invasive
weeds in imagery, review the evidence, and turn findings into a useful plan for
field verification. It also helps specialists curate reliable reference
collections so the service can improve across species, places, and viewpoints.

The first release should deliver one dependable assessment workflow for a pilot
partner. New Zealand is the proposed first geography, with gorse as a provisional
target species. The partner, species, area, and supported imagery conditions
remain product decisions to confirm. This document describes the intended
product; the existing research prototype does not establish readiness for field use.

## Problem

Conservation teams have limited time to inspect large areas and assess imagery.
Small or unfamiliar infestations can be missed, while uncertain identifications
and false alarms consume specialist time. Images and observations arrive from
different sources, dates, viewpoints, and levels of quality. An identification
that is convincing in one photograph may be difficult to recognise from above.

Teams need a practical way to distinguish promising leads from verified findings,
understand where the evidence is weak, and hand useful information to field staff.
They also need reviewed examples they can trust and improve without losing the
original evidence or the reasons behind a correction.

These are working problem hypotheses. Pilot discovery must establish the current
assessment process, its cost, and the consequences of missed weeds and false alarms.

## Users and their jobs

| User | Job to accomplish | What a good outcome looks like |
| --- | --- | --- |
| Land manager or conservation coordinator | Decide where to send limited survey effort | A clear, prioritised set of findings with usable locations and visible uncertainties |
| Ecologist or weed identification specialist | Verify species and the extent visible in imagery | Enough context to confirm, correct, reject, or defer a finding without losing evidence |
| Imagery reviewer | Work through an assessment efficiently and consistently | Clear review progress, saved decisions, and an easy way to add missed findings |
| Collection steward | Maintain trustworthy examples for supported species and conditions | Original evidence, accountable corrections, clear reuse conditions, and visible coverage gaps |
| Field surveyor | Locate and verify suspected infestations | A concise handoff with imagery, location quality, target species, and the reason for the visit |

A small pilot team may fill several of these roles. Separate responsibilities
matter when specialist review is needed or people disagree about a finding.

## Goals

1. Reduce the total effort required to produce a useful weed assessment, including
   the time spent checking false alarms and correcting missed findings.
2. Help teams find infestations they would otherwise miss or discover later.
3. Make uncertainty, evidence quality, and review status understandable at the
   point where someone makes a decision.
4. Produce a handoff that a field team can use to plan and conduct verification.
5. Build reviewed reference collections that improve coverage of different
   species, habitats, seasons, image sources, and viewing angles.
6. Expand support only where the product demonstrates useful performance for the
   intended users and conditions.

## Initial release scope

The proposed pilot covers one target species, a defined geographic area, and an
agreed set of imagery conditions. Its central workflow is assessment, review,
and field handoff. A manageable reference collection supports that workflow.
The pilot should include examples from more than one location so a successful
demonstration at a single site is not mistaken for broad reliability.

The product should accommodate useful aerial and ground imagery as support
expands, while making each source's capabilities and limitations clear. A ground
photo may support species identification without supporting an infestation map.
An aerial image may support a visible patch boundary without resolving every
small plant. Users must understand what the product can conclude from their input.

The pilot handoff can include existing field evidence supplied with a finding.
Capturing new survey results within Weedz and feeding them into subsequent
assessments are later capabilities; the initial release delivers the verification
worklist and preserves the evidence already available.

### Required for the pilot

- Set up an assessment with its target species, area or photo collection, imagery
  dates where known, and intended use.
- Understand whether the supplied evidence is suitable for the requested assessment.
- Inspect likely findings in the original imagery and their surrounding context.
- Confirm, correct, reject, or leave a finding unresolved; add missed findings.
- Keep progress, specialist questions, and review decisions understandable.
- Distinguish proposed findings, image-confirmed findings, and field verification.
- Share an assessment summary and actionable field-verification list.
- Curate examples and corrections with their source, reuse conditions, and reasons.
- See where product support and reference coverage are strong, limited, or unassessed.

### Later opportunities

Broader species and regional coverage, more imagery conditions, assessments over
time, field-result feedback, team coordination at larger scale, and regional
screening may follow demonstrated pilot value. Video support and live field
assistance are future opportunities rather than requirements for the first release.

### Outside the first release

Universal identification of every weed from every image, claims that unreviewed
land is weed-free, execution of weed treatment, and a general public biodiversity
platform are outside the initial scope. The product supports assessment and
verification; the pilot does not include treatment planning or treatment efficacy claims.

## Core user journeys

### 1. Assess an area or collection

A coordinator selects the target species and supplies an area or image collection.
They see the relevant coverage, dates, missing information, and supported uses.
If some imagery is unsuitable, they can understand why and decide whether to
replace it, narrow the assessment, or continue with a clearly limited result.
The assessment has a visible purpose, owner, and review progress.

### 2. Review likely weeds

A reviewer inspects each proposed finding in context. They can confirm the
species visible in the image, correct the identification or boundary, reject the
finding, add an overlooked plant or patch, or request specialist help. They can
inspect areas without proposed findings to check for misses.

Progress is saved so work can be resumed. An unresolved identification remains
visible, with the evidence or expertise needed to resolve it. A change to an
earlier decision preserves the reason and makes the current decision clear.

### 3. Prepare field verification

The coordinator reviews a summary of confirmed, proposed, rejected, unresolved,
and unassessed results. They prioritise visits using management importance,
uncertainty, and location usefulness. The field team receives the target species,
supporting image, relevant dates, location quality, and the reason for each visit.
The handoff distinguishes image review from evidence collected on the ground.

### 4. Improve a reference collection

A steward selects examples for a supported species and checks identity, image
usefulness, viewing conditions, and reuse eligibility. A specialist can accept,
correct, dispute, or exclude an example while preserving the original evidence.
The steward can see which habitats, growth stages, viewpoints, and locations
remain poorly represented and organise collection or review work to fill those gaps.

## Product requirements

All requirements below are proposed pilot requirements. Their acceptance criteria
describe user-observable outcomes rather than how the product is built.

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| P01 | Define an assessment | Users can identify the target species, assessment scope, purpose, and responsible person and can distinguish separate assessments |
| P02 | Explain input suitability | Before relying on results, users can see supported conditions, relevant dates, missing information, and any part of their input that cannot be meaningfully assessed |
| P03 | Accommodate different evidence | A supported photo or aerial assessment provides an appropriate result; a missing location does not create a fictitious map position, and a photo location is not presented as a patch boundary |
| P04 | Present reviewable findings | A finding can be inspected alongside the original image and surrounding context, with the proposed identity and known uncertainty understandable |
| P05 | Support meaningful corrections | Reviewers can change identity, adjust a visible boundary where applicable, reject a finding, add a miss, or defer a decision with a reason |
| P06 | Preserve uncertainty and coverage | Proposed, image-confirmed, rejected, unresolved, and unassessed results are distinguishable; lack of a finding does not imply verified absence |
| P07 | Support ongoing review | Users can resume work, see completed and remaining review, identify specialist questions, and understand disagreements and their eventual resolution |
| P08 | Keep decisions accountable | A reviewed finding retains its source evidence, relevant dates, current decision, reviewer, and the reasons for material changes |
| P09 | Produce a useful handoff | Users can share or download a summary and finding list usable in the pilot partner's existing mapping and reporting work, with review status and source attribution preserved |
| P10 | Prioritise field effort | A coordinator can choose which findings need visits and record why; field staff can distinguish suspected and image-reviewed findings from any supplied field verification |
| P11 | Curate reliable examples | Stewards can distinguish original evidence from accepted corrections, identify unsuitable or disputed examples, and understand which examples are eligible for reuse |
| P12 | Expose coverage gaps | Users responsible for quality can see collection coverage and demonstrated product support by species, place, viewing conditions, habitat, and season where information is available |
| P13 | Communicate reliability honestly | Product claims apply to the species and conditions actually assessed; users can see important known limitations before making a decision |
| P14 | Respect source restrictions | Shared findings and collections preserve required attribution and any restrictions on reuse or precise locations; the product does not reveal more location detail than users are entitled to receive |
| P15 | Work for the intended reviewers | Core review actions are keyboard-accessible, decisions are not communicated by colour alone, and users can read uncertainty and status without specialist software knowledge |

## Product behavior in difficult cases

| Situation | Expected experience |
| --- | --- |
| The species is unfamiliar or visually ambiguous | Mark the finding unresolved and explain that more evidence or specialist review is needed |
| Imagery is too old, unclear, or taken from an unsupported viewpoint | Explain the limitation and identify affected results or areas; allow a narrower assessment where useful |
| Only part of an area can be assessed | Show the assessed and unassessed coverage separately and carry that distinction into the handoff |
| A reviewer finds a weed where none was proposed | Let them add the finding and include it in the same review and reporting workflow |
| Two reviewers disagree | Preserve the disagreement, allow referral to a specialist, and show the decision that currently governs the assessment |
| Several images show the same encounter | Keep the evidence together so repeated views do not misleadingly appear to be several independent infestations |
| An image supports identification but not a reliable ground location or boundary | Provide the identification evidence and its limitations without inventing geographic precision |
| Source rights or location permissions are unclear | Make the restriction visible and keep affected material out of uses that require unresolved permission |

## Success measures

The primary outcome is less total effort to produce an assessment useful for
field verification, while maintaining an agreed standard for finding important
infestations. Measure the complete workflow, including review and correction,
rather than the speed of producing initial suggestions alone.

| Measure | How it is assessed | Pilot success condition |
| --- | --- | --- |
| Time to a planning-ready assessment | Compare total coordinator/reviewer effort with the partner's manual process on comparable work | Lower effort without a worse rate of consequential missed infestations |
| Infestations found and missed | Compare results with an independently reviewed reference within the declared assessment scope | Meets species- and condition-specific limits agreed before the pilot |
| False-alarm burden | Count rejected suggestions and the review effort they consume | Fits the partner's agreed review capacity and still reduces total work |
| Handoff completeness | Inspect findings delivered to field teams for evidence, status, dates, and usable location information where available | Every finding communicates its evidence and known limitations |
| Review usability | Observe intended reviewers completing setup, review, correction, and handoff | Users complete the core journey without ongoing assistance from the product team |
| Reference quality and coverage | Independently inspect accepted examples and identify missing conditions | Accepted examples meet the agreed review standard and remaining gaps are visible |
| Operational usefulness | Follow whether the partner uses findings to select and conduct verification work | The output supports an actual planning decision and a useful field handoff |

Numeric limits for missed infestations, false-alarm workload, turnaround, and
improvement over the manual process must be agreed with the pilot partner before
the pilot begins. They depend on the target species, smallest infestation worth
reporting, imagery conditions, and available review effort. These are unresolved
launch criteria, not a universal accuracy promise. A pilot is not successful merely
because it produces more detections or performs well on familiar examples.

## Pilot and release readiness

1. **Problem validation:** confirm the partner, primary users, target species,
   current workflow, and decision the product should improve.
2. **Scope agreement:** define the area, supported imagery conditions, reportable
   infestations, verification process, review responsibilities, and success limits.
3. **Assisted pilot:** complete real assessments with users, observe review effort,
   and record misses, false alarms, confusion, and field usefulness.
4. **Independent assessment:** establish whether results meet the agreed limits
   in locations and conditions representative of the intended use.
5. **Limited release:** make the workflow available for the demonstrated scope,
   with clear limits, accountable review, and a way to report problems.

Expansion to another species, geography, or viewing condition requires evidence
that the product remains useful there. Improvements to a familiar example
collection do not establish broader readiness.

## Assumptions and open product decisions

- Which organisation and user own the first planning decision?
- Is gorse the right initial target, and which region provides a useful pilot?
- Is the first priority aerial assessment, ground-photo identification, or a
  combined workflow, and what imagery can the partner already supply?
- What is the smallest or least visible infestation that matters operationally?
- How costly are missed infestations compared with wasted verification visits?
- Who can confirm species identity, resolve disputes, and declare review complete?
- What turnaround and review effort can the team sustain?
- What evidence is needed to distinguish image confirmation from field verification?
- What must a report contain to fit the partner's existing planning and mapping work?
- What sharing, attribution, and location restrictions apply to pilot evidence?
- What commercial or funding arrangement would make repeated use sustainable?

These decisions refine the pilot scope and launch criteria. Model selection,
data processing, infrastructure, and other implementation choices are outside
this PRD.
