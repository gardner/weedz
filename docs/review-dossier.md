# NZ weed photo pilot — reviewer brief

We’re checking whether ordinary New Zealand photos contain identifiable weeds,
including plants in the background. We’re also testing how easy the review
tool is to use. Base each submission on what you can see in the photo.

## Open your assigned review

Sign in to **CVAT** with your own account and open the job in the column
assigned to you. If a job denies access, give the coordinator your CVAT
username so they can assign it. If you’re doing both handheld jobs, finish
the blind job first.

| Review | Reviewer A | Reviewer B |
| --- | --- | --- |
| Vegetation-focused blind, 12 photos | [Open job A](https://cvat.llm.nz/tasks/17/jobs/29) | [Open job B](https://cvat.llm.nz/tasks/17/jobs/30) |
| Vegetation-focused assisted, 12 photos | [Open job A](https://cvat.llm.nz/tasks/18/jobs/26) | [Open job B](https://cvat.llm.nz/tasks/18/jobs/27) |
| Optional camera review, 1 photo | [Open job A](https://cvat.llm.nz/tasks/13/jobs/14) | [Open job B](https://cvat.llm.nz/tasks/13/jobs/15) |
| Optional camera review, 2 photos | [Open job A](https://cvat.llm.nz/tasks/14/jobs/17) | [Open job B](https://cvat.llm.nz/tasks/14/jobs/18) |

## What to look for

| Common name | Name in CVAT |
| --- | --- |
| Gorse | *Ulex europaeus* |
| Old man’s beard | *Clematis vitalba* |
| Pampas grass | *Cortaderia selloana* |

Work independently. In assisted or camera jobs, the task guide lists the
suggested name for each image and the contextual image shows the search crop.
Use both as clues and inspect the full photo, including areas outside the crop.
Open any linked source observation only after saving your review of that photo.
[CVAT contextual images](https://docs.cvat.ai/docs/annotation/manual-annotation/utilities/contextual-images/)

## Review each photo

1. **Inspect the full photo.** Zoom in as needed. Check the background, margins
   and vegetation around the main subject. Use the **Tag** tool to add one
   **Photo review** tag. Set its **Any plants** attribute to **Visible**,
   **None visible** or **Unsure**.
2. **Set the Watchlist attribute.** Choose **Visible** if you can identify at
   least one of the three listed species. Check every species you can identify.
   Choose **None visible** when the photo is clear enough for you to judge that
   none is visible. Choose **Unsure** when blur, distance, occlusion or a
   lookalike prevents a confident answer.
   If one species is identifiable and a second is uncertain, select the
   identifiable species and mention the uncertainty in your notes.
3. **Set the Other plants attribute.** Use **Visible** when you can see a plant
   outside the watchlist, even if you cannot name it. Use **None visible** or
   **Unsure** as appropriate. Complete all three attributes before moving on.
4. **Mark identifiable plants on the full photo.** Brush the visible part of
   each watchlist plant you can locate and choose its species label. Leave
   hidden parts unpainted. Use **Other plant** for a visible region you can
   place outside the watchlist and **Unknown** for an unresolved region you
   can locate. If you cannot place a boundary, keep your photo-level answer
   and mention it in your notes. Save your changes in CVAT.

## Tell us how the review went

Record your review time, interruptions, unclear instructions, loading or zoom problems, and
anything that made it hard to identify or mark a plant. In your notes, include
the job link and image number so we can find the example. After finishing,
save your job and give your notes to the pilot coordinator.
