# Weedz: a second look at everyday photos

Target: three minutes, 1920×1080, captions, original Breeze narration and an
original Music3 instrumental. `narration.json` is the canonical timed edit and
records the selected source utterances. Generated media stays outside Git.

| Time | Picture | Purpose |
| --- | --- | --- |
| 0–13 s | Static public skink photograph | Ask what else an ordinary photograph captures |
| 13–42 s | Overlapping search windows and watchlist | Explain actual full-frame/tile screening |
| 42–70 s | Recorded review desk and original screenshots | Show evidence and human assessment |
| 70–90 s | Minimal report fields beside a public plant photo | Identification suggestion, recorded location and model score; photo optional |
| 90–111 s | Actual running app Settings and HTTPS deletion | Show real control after sharing |
| 111–135 s | Person → intake → specialist | Explain consent, provenance and withdrawal |
| 135–157 s | Full pilot sample counts and remaining proof | Distinguish measured samples from detection accuracy |
| 157–180 s | Project invitation and credits | Sources, creator attribution and generated-audio disclosure |

## Production choices

Use the real review application on an independent copy of source-eligible public
photos, preserving original model scores. The app footage uses release-compiled
Flutter web, actual secure storage and an actual local HTTPS intake. No mock
transport, widget fixture, seeded app screen or fake operational URL appears.
Keep source coordinates, credentials and personal photos out of all frames.

Keep the presentation clean: no demo/prototype banners or production annotations.
Photos stay still; there is no Ken Burns effect. Give photo attribution and full
source links in the credits and companion record. The generic narration voice
is generated with Breeze TTS 2, without EQ, normalization or speed changes.

## Evidence and remaining capability

The benchmark compared 30 pilot photographs and 39 source-labelled lookalikes;
these convenience samples do not establish population accuracy. The curated
capture subset has different counts and is not a new evaluation. The actual
screen uses BioCLIP 2 with whole-frame and overlapping-tile analysis, with no
segmentation. Search-window drawings explain that method; they are not masks.

The camera-roll scan UI, native inference/runtime and device parity remain
separate implementation work. The movie does not show them operating or replace
them with a fake scanner. Report simplification is tracked in #121, segmentation
in #122. The mobile scene demonstrates the working settings/deletion capability.

#112 is complete only after delivery of the MP4, captions, attribution and
reproduction instructions, with full decode and media checks. Do not commit
rendered video, audio, downloaded photos or model checkpoints.
