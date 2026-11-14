# Weedz: a second look at everyday photos

Target: about three minutes, 1920×1080, with captions and an original generic female
narration voice. Actual review footage and Flutter prototype screens must remain
recognisable as the product. Do not imply that native phone inference, battery
performance, a validated detection rate or new weed localities have been demonstrated.

## Story and capture plan

| Time | Picture | Narration direction |
| --- | --- | --- |
| 0–18 s | A source-eligible ordinary photo; gently reveal background vegetation | What else did this photograph capture? A bird, a walk, a day by the coast—and perhaps a plant worth a second look. |
| 18–42 s | Photo → overlapping windows → shortlist animation | Weedz explores whether photographs taken for another purpose can help people find invasive plants. It examines the whole frame and overlapping smaller views, then suggests photographs for a person to check. |
| 42–65 s | Real review desk, image and candidate window; include a lookalike/false alarm | A suggestion is not an identification. Native plants can resemble weeds, and the model can be wrong. The review desk keeps the original image, the suggested region and the evidence together, so a specialist can judge what is actually visible. |
| 65–93 s | Real Flutter approval widgets, clearly marked phone prototype | The phone prototype starts with a simple promise: your library belongs to you. The design screens on the phone. Only an individual report that you approve is intended to leave it. Native phone inference still needs to pass its performance and parity checks. |
| 93–120 s | Interact with actual approval controls; remove photo/location | Before approving, see the information that would be shared. Remove a photo or its location. Photo permissions are separate choices. Finding a possible weed should not mean surrendering the rest of your photographs. |
| 120–144 s | Device → intake → specialist animation; connect to real review footage | Approved reports have a separate intake path. Their source, model and consent travel with them. The specialist review step turns a machine suggestion into a documented human assessment, rather than an automatic claim. |
| 144–166 s | Current measured pilot facts and remaining work | The pilot has tested a small, source-labelled collection and recorded real failures as well as promising suggestions. These results guide the next experiments; they do not establish a detection rate for everyone's photo library. The next proof is useful findings, checked by people, at a manageable review cost. |
| 166–180 s | Source/photo/audio credits and project URL | Weedz is open-source work for conservation. Help test the question, review the evidence, and turn an overlooked background into a reason to take a second look. |

## Evidence and truth labels

- Use the latest sections of `docs/pilot-nelson-tasman.md` and
  `benchmarks/model-comparison.json` when writing on-screen numbers. The benchmark
  says the same 30 pilot photos and 39 source-labelled lookalikes were compared;
  these are convenience samples, not a population accuracy estimate.
- `docs/pipeline.md` includes target architecture and an outdated introductory
  model description. Do not show planned segmentation/SAM as implemented.
- The mobile app currently has a shell and approval widgets. The scan/library,
  specialist device-report integration, rights and deletion work have separate
  in-flight PRs. Capture the actual merged state or explicitly label an unmerged
  prototype; do not fabricate working backend interactions.
- No contributed private photos, bearer tokens, signing settings, personal
  library screenshots or exact source coordinates in the video.
- Record the source URL, creator, licence and allowed use for every photo and
  soundtrack. Display attribution/credits in the video and accompanying file.
- Generated narration is a generic voice design, not a clone of any real person.

## Production notes

Audio experiments use an isolated environment and GPU 0; the screening project's
CPU dependencies and other sessions' worktrees remain untouched. Breeze TTS 2
and MiniMax Music 3 are the first candidates to evaluate, per #112. Read their
licences before producing or distributing audio and record pinned revisions and
prompts. Large model files and rendered video/audio belong outside Git.

This storyboard is a production input. #112 is not complete until a viewable MP4,
captions, attribution and reproduction instructions have been delivered and checked.
