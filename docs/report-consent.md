# Report consent text

This is the wording the app shows before a person approves a report. Each version is
published here and never edited once devices use it. A changed wording is a new version
section, and its id is added to `VERSIONS` in `src/weedz/consent.py`. A report names the
version its person saw (`consent.wording_version`), and the intake refuses a version
that isn't published here. The intake keeps that version and the uses the person
permitted, including after they withdraw the report.

How the choices are enforced:

| Use | What it allows | Where it is checked |
|-----|----------------|---------------------|
| `review` | Specialists look at the photo to check the suggestion | Required for any photo. The review app shows a device photo only with it (`sharing.image_use`) |
| `evidence` | The photo is kept after its review, as evidence of the finding | Recorded now. Deletion after review closes follows with the review lifecycle (#58) |
| `agencies` | The photo goes into packages and exports shared with weed agencies and partners | `sharing.image_use(..., "share")`, so run exports, follow-up packages and suitability summaries. Reference-collection sharing |
| `public` | The photo may be published openly, e.g. in an open dataset or on GBIF | Nothing publishes today. Any future public outlet must check it |
| `training` | The photo trains and tests weed-finding models | Reference-collection training and evaluation eligibility |

A withdrawn report permits none of these. Material from sources such as iNaturalist has
no consent record and stays governed by its own licence (`docs/datasets.md`).

Defaults (decisions pending on #60): only `review` is ticked, the licence offered first
is CC BY-NC, and the credit name is empty, which credits "a Weedz contributor".

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
