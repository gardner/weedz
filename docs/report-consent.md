# Report consent text

This is the wording the app shows before a person approves a report. Each version is
published here and never edited once devices use it. A changed wording is a new version
section, and its id is added to `VERSIONS` in `src/weedz/consent.py`. A report names the
version its person saw (`consent.wording_version`), and the intake refuses a version
that isn't published here. The intake keeps that version and the uses the person
permitted, including after they withdraw the report.

Consent to share a report's exact location is #91 (PR #105).

How the photo choices are enforced:

| Use | What it allows | Where it is checked |
|-----|----------------|---------------------|
| `review` | Specialists look at the photo to check the suggestion | Required for any photo. The review app shows a device photo only with it (`sharing.image_use`) |
| `evidence` | The photo is kept after its review, as evidence of the finding | Recorded now. Deletion after review closes follows with the review lifecycle (#58) |
| `agencies` | The photo goes into packages and exports shared with weed agencies and partners | `sharing.image_use(..., "share")`, so run exports, follow-up packages and suitability summaries. Reference-collection sharing |
| `public` | The photo may be published openly, e.g. in an open dataset or on GBIF | Nothing publishes today. Any future public outlet must check it |
| `training` | The photo trains and tests weed-finding models | Reference-collection training and evaluation eligibility |

A withdrawn report permits none of these. Material from sources such as iNaturalist has
no consent record and stays governed by its own licence (`docs/datasets.md`).

Current defaults (#121): no photo, photo licence, photo permissions or credit are
sent. A recorded photo location with known accuracy is included and displayed,
with an obvious removal control. Optional photo sharing requires a chosen licence;
`review` is its only permitted use in this screen.

## Version 2026-11-15

**Report sighting** approves and sends the suggested species, raw model score,
model version and available capture time shown above. The score is not a calibrated
probability or confirmed identification. Nothing is sent before you press this button.

**Location:** the exact recorded photo location and its accuracy are shown before
the button. It is included when available; choose **Remove the location** to omit
it. We do not substitute the phone's current GPS or invent an accuracy. People who
check and follow up sightings can see the included point.

**Photo (optional):** no photo is sent by default. If you choose **Send this photo**,
first check the preview and choose a licence. An unreadable crop cannot be attached.
A specialist can use an attached crop to review the suggestion. This screen grants
no evidence-retention, agency-photo-sharing, public-publication or training permission.
The photo licence options are CC BY-NC 4.0 (credit, noncommercial reuse), CC BY 4.0
(credit, any reuse), and CC0 1.0 (no rights reserved). A supplied credit name is shown
and sent only with an attached photo. Removing the photo also removes its licence,
photo permissions and credit. Structured report details remain the sighting report.

**Changing your mind:** after sending, retrying preserves the same id and content.
You may withdraw the report; the intake deletes its identifying report details and
crop, retaining only a non-identifying id/time tombstone and consent version/use
audit. Already distributed copies cannot be recalled. Device-wide deletion and
lost-phone requests are described in [device deletion](device-deletion.md).

This screen and its consent flow are implemented independently of native scan and
runtime wiring; a production intake and public privacy contact still need deployment.

## Version 2026-11

> Draft for review before the app ships it (#60). Bracketed text is to be confirmed.

**Sending this report**

You're sending us a possible sighting of a weed: the suggested species, the score the
app gave it, where your phone was and when the photo was taken. The location is
exact, because that's what lets someone find and check the plant. You can see all of
it above before you send. Sending is up to you, and nothing is sent until you approve.

**Your photo (optional)**

If you include the cropped photo, a specialist will look at it to check the suggestion.
We remove all hidden data (camera details, GPS tags) from the photo before we store it.
You can also choose what else it may be used for. Each choice is separate, and all of
them start off:

- `evidence`: keep the photo after it has been checked, as evidence of the finding.
- `agencies`: share the photo with weed agencies and partners who act on sightings,
  such as regional councils [list to be confirmed].
- `public`: publish the photo openly, for example in an open biodiversity dataset.
- `training`: use the photo to train and test the app's weed-finding model.

The location and details of the report are shared with agencies whenever the report is
followed up. They're the point of the report.

**Licence and credit**

Choose the licence your photo and report details are shared under: CC BY-NC 4.0
(others may reuse them non-commercially, crediting you), CC BY 4.0 (any reuse, crediting
you) or CC0 1.0 (no rights reserved). Add the name you'd like to be credited as, or
leave it blank to be credited as "a Weedz contributor". We'll show the credit as
"Photo: <your name> via Weedz, <licence>".

**Changing your mind**

You can withdraw a report from the app at any time. We then delete the photo and the
report's details straight away, and use them for nothing further. We keep a record
that a report was received and withdrawn, under which version of this text, and which
uses you had allowed, but not your name, the photo, the location or the species. Copies
already shared with an agency, and models already trained, can't be recalled. A
withdrawn photo is left out of every later training run and package.

**Your information**

We collect this to find and check weed sightings in [the pilot region]. Under the
Privacy Act 2020 you can ask to see or correct the information we hold about you:
contact [privacy contact to be confirmed].
