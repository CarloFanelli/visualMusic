---
feature: point-proposals
version: 1.0
status: approved
completed: true
base: c663456b738beee621865590ed11d00b47846dcc
---

# Point Proposals

## Overview

Reduces annotation work by having a trained model suggest the four points on each pending image. The user sees the points already placed, moves only the wrong ones, and confirms with one key. Images where the model finds no saxophone are marked by hand at the end. Nothing becomes training data without the user's confirmation. A command trains the model fully, and another computes the suggestions, so the cycle can repeat as annotations grow.

## Project Context

- Builds on the existing local annotation page, manifest, annotations and export.
- The four points are bell centre, two bell-edge points and kiver.
- The model always returns four points and cannot reliably tell when one is hidden.
- The model finds no saxophone on about one pending image in five.
- Images showing several saxophones stay rejected by the user, as today.
- Images and videos never go to GitHub; model files stay local.
- Training runs on an Apple M1 Pro; the page stays reachable only from this computer.
- Project documents are in English; the page stays in Italian.

## Functional Requirements

### Training and proposals

- REQ-1: A command trains the model for 100 passes on the exported dataset and makes the result the model used for proposals.
- REQ-2: A command computes a proposal for every pending image using the latest trained model and stores it locally.

### Reviewing a proposal

- REQ-3: A pending image with a proposal opens showing its four points already placed, with no click needed.
- REQ-4: Dragging a point moves it inside the image and leaves the other points where they are.
- REQ-5: Selecting a point from a list, then clicking the image, moves that point to the clicked position.
- REQ-6: The user can mark the selected point as not visible, and restore it by placing it again.
- REQ-7: Annulla reverts the last move or hide on the current image.
- REQ-8: Pressing Enter or Conferma saves the shown points as an annotation and opens the next image.
- REQ-9: Only a confirmation creates an annotation; export and training never read proposals.
- REQ-10: Salta and Non adatta work on an image with a proposal exactly as on any other image.

### Order and images without a proposal

- REQ-11: Pending images with a proposal open first; those without open afterwards, marked by today's point-by-point clicks.
- REQ-12: Progress shows how many pending images have a proposal and how many do not.
- REQ-13: Reopening an annotated image shows its saved points, movable the same way and saved with Conferma.

## Data & Dependencies

### Information the feature must retain

- Proposal: the model's suggested points for one pending image; regenerable, local, not versioned, replaced when proposals are recomputed, and ignored once the image has an annotation.
- Latest trained model: local file used for proposals; replaced only when a new training succeeds.
- Annotation: unchanged in meaning and format, so existing annotations and export keep working.

### External capabilities relied on

- Keypoint model training and prediction — trains the model and computes proposals.

## Non-Functional Requirements

- **Performance** — The next image appears with its points within 500 ms of confirming, on the M1 Pro.
- **Performance** — Computing proposals for 1,000 images finishes within 5 minutes on the M1 Pro.
- **Security** — Proposals and model files never leave the computer and stay out of git.
- **Validation** — Stored points always lie inside their image bounds.

## Edge Cases & Error Handling

| Edge Case | Expected Behavior | Relates to |
|-----------|-------------------|------------|
| Exported dataset is missing | Training stops and names the export command | REQ-1 |
| Training fails or is interrupted | The previous model stays in use and the error is shown | REQ-1 |
| Apple GPU fails during training | Falls back to CPU with a visible notice | REQ-1 |
| No trained model exists | Proposal command stops and names the training command | REQ-2 |
| Model finds no saxophone in an image | No proposal is stored; the image counts as without proposal | REQ-2 |
| Model finds more than one saxophone | The most confident one is proposed; the user rejects the image if it shows several | REQ-2 |
| Image file is missing or unreadable | Reported and counted; the other images continue | REQ-2 |
| Command runs again after new training or collection | Pending images get fresh proposals; annotations stay unchanged | REQ-2 |
| Command is interrupted | Earlier proposals stay usable; running again completes the rest | REQ-2 |
| Predicted point falls slightly outside the image | It is placed on the nearest image edge | REQ-3 |
| Photo has rotation metadata | Points appear on the same spot of the upright image shown | REQ-3 |
| Proposal file is unreadable or uses other point names | Treated as no proposal; the image is marked by hand | REQ-3 |
| Proposal cannot be fetched from the page | The image opens for clicking by hand, with a message | REQ-3 |
| Point is dragged beyond the image | It stops at the image edge | REQ-4 |
| Several points overlap | Dragging moves the top one; the list reaches the others | REQ-4, REQ-5 |
| No point is selected and the image is clicked | Nothing changes, so a stray click never moves a point | REQ-5 |
| Selected point is hidden and the image is clicked | The point becomes visible at that position | REQ-6 |
| Every point is marked not visible | Cannot be confirmed; the user is asked to reject the image or undo | REQ-6, REQ-8 |
| Annulla with no change made | Nothing changes | REQ-7 |
| Enter is held down | Only one image is confirmed | REQ-8 |
| Enter is pressed again as the next image appears | Ignored for the first 300 ms, so no image is confirmed unseen | REQ-8 |
| Enter or Conferma before the image has loaded | Ignored | REQ-8 |
| Focus is on another button when Enter is pressed | Enter confirms and that button does not fire | REQ-8 |
| Saving fails | Stays on the image, keeps the moved points, shows an error and retry | REQ-8 |
| Last image is confirmed | Shows completion and the remaining skipped count | REQ-8 |
| Same image is open in two tabs | The last save wins | REQ-8 |
| Page is reloaded before confirming | Moves are discarded; the image shows its proposal again | REQ-9 |
| Proposal exists but the image has never been confirmed | Image stays pending and is left out of export | REQ-9 |
| Skipped image returns later | It opens with its proposal | REQ-10 |
| Rejected image is restored | It becomes pending and opens with its proposal, if any | REQ-10 |
| No proposals exist at all | Every image is marked by hand, as today | REQ-11 |
| Only images without a proposal remain | They open one by one for clicking | REQ-11 |
| Proposals are recomputed while the page is open | Counts update on reload; the next image uses the newest proposal | REQ-12 |
| Reopened image is left without confirming | Its saved points stay unchanged | REQ-13 |
| N/A — permission and network: one local user on this computer, no remote service | — | REQ-1, REQ-2 |

## Out of Scope

- **Grid confirmation of many images at once** — the user chose one image at a time, because small errors escape on thumbnails.
- **Guessing hidden points automatically** — the model's confidence does not separate hidden points from visible ones.
- **Proposing several saxophones per image** — such images stay rejected, as in the existing rule.
- **Zooming the image** — not requested; it can follow if small saxophones prove hard to correct.
- **Recording whether a proposal was moved or accepted** — not needed to annotate; it can follow if needed to measure the model.
- **Final model evaluation on an unseen video** — this feature only speeds up annotation; quality is judged next.
