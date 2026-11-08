---
feature: sax-dataset
version: 1.0
status: approved
completed: true
base: 0b6e0f90aeb5b52174db8bc5e3034b76095ef453
---

# Sax Dataset

## Overview

Prepares everything needed to train a model that locates the sound-emitting point of a saxophone. It installs the training environment, collects tenor and alto saxophone images under safe licenses with attribution, adds frames from the user's own videos, and provides a local web interface for marking four points per image. It ends with an annotated dataset and a short trial training that proves the data is usable. Model quality is judged in a later feature.

## Project Context

- Personal project, open to future contributors; the GitHub repository is private.
- Training runs on an Apple M1 Pro with 16 GB of memory.
- The model is Ultralytics YOLO, whose AGPL-3.0 terms apply if the project is distributed.
- Only images free of copyright problems are allowed: CC0, public domain or CC BY.
- Licenses are those declared by each source; this reduces legal risk but gives no absolute guarantee.
- The four points are bell centre, two opposite bell-edge points, and mouthpiece.
- Project documents are in English; commits never mention AI.

## Functional Requirements

### Environment

- REQ-1: One documented command installs the training environment on Apple Silicon, isolated from the system Python.
- REQ-2: An environment check reports the installed YOLO version and whether Apple GPU acceleration is available.

### Image collection

- REQ-3: A command collects candidate saxophone images from Wikimedia Commons, Open Images and Openverse.
- REQ-4: Collection keeps only CC0, public domain and CC BY images, rejecting every other license and reporting rejection counts by reason.
- REQ-5: Every kept image has a manifest record with source URL, author, license, license URL, collection date and file fingerprint.
- REQ-6: Re-running collection adds only new images and leaves existing manifest records unchanged.
- REQ-7: A command restores missing online-sourced image files from the manifest, so a fresh clone can resume annotation.
- REQ-8: A command extracts frames from videos supplied by the user and records them in the manifest as user-owned.
- REQ-9: Image and video files stay out of git, while the manifest and annotations are versioned.

### Annotation interface

- REQ-10: A page on localhost lists every candidate image with its status (pending, annotated, skipped, rejected) and shows overall progress.
- REQ-11: The page requests points one click at a time, in the order set by an editable instrument definition file.
- REQ-12: After the last point, the annotation saves automatically and the next pending image opens.
- REQ-13: The user can undo the last point, skip an image for later, or reject it as unsuitable.
- REQ-14: The user can mark any single point as not visible instead of placing it.
- REQ-15: Saved work survives restarts; the interface resumes at the first pending image, and saved points can be reopened and changed.

### Dataset and trial

- REQ-16: An export command builds a YOLO keypoint dataset with training and validation splits, from annotated images only.
- REQ-17: The finished dataset contains at least 300 annotated images, including at least 50 from the user's videos.
- REQ-18: A trial training runs on the exported dataset and saves a model file.
- REQ-19: The trial produces validation images with predicted points drawn on them, for visual inspection.

## Data & Dependencies

### Information the feature must retain

- Image manifest: one record per candidate image, created at collection or extraction and kept as the license and attribution proof.
- Annotations: points and visibility per image, created when annotated, changed on correction; rejected images keep their status.
- Instrument definition: the ordered point names for an instrument, changed only by hand.
- Image and video files: local only, restorable from the manifest when sourced online.
- Exported dataset and trial results: regenerable output, not versioned.

### External capabilities relied on

- Open image catalogues with declared licenses — provide candidate images and license information.
- Keypoint model training — trains and runs the trial model.
- Video frame extraction — turns the user's videos into images.

## Non-Functional Requirements

- **Performance** — The next image appears within 500 ms of the last click on the M1 Pro.
- **Performance** — The trial training finishes within 30 minutes on the M1 Pro.
- **Security** — The annotation interface is reachable only from the same computer, and uploads no image anywhere.
- **Validation** — Stored points always lie inside their image bounds.
- **Validation** — The object box YOLO requires is derived automatically from the visible points, with no extra clicks.

## Edge Cases & Error Handling

| Edge Case | Expected Behavior | Relates to |
|-----------|-------------------|------------|
| Setup is run a second time | Reuses the environment and ends successfully | REQ-1 |
| Network drops during installation | Stops with a clear error; re-running completes the install | REQ-1 |
| Apple GPU is unavailable | Check reports CPU-only with a warning, without failing | REQ-2 |
| Environment is not installed | Check tells the user to run setup | REQ-2 |
| One source is unreachable | Collection continues with the others and names the failed source | REQ-3 |
| A source asks to slow down | Collection waits as requested and retries; it never bypasses the limit | REQ-3 |
| A source returns no results | Reports zero for that source and continues | REQ-3 |
| License is missing or unrecognised, such as GPL or GFDL | Image is rejected and counted by reason | REQ-4 |
| License is CC BY-SA, NC or ND | Image is rejected and counted by reason | REQ-4 |
| CC BY image has no identifiable author | Image is rejected, since attribution cannot be kept | REQ-5 |
| Download fails | No manifest record is created for that image | REQ-5 |
| Same image is found in two sources | Kept once, detected by file fingerprint | REQ-6 |
| Collection is interrupted | Re-running continues without duplicates | REQ-6 |
| Source has removed an image | Reported as missing and left out of export; its annotation is kept | REQ-7 |
| Restored file differs from its fingerprint | Treated as missing and not used | REQ-7 |
| User-owned frame is missing | Reported as restorable only from the user's video | REQ-7 |
| Video file is unreadable | Error names the file; other videos continue | REQ-8 |
| Same video is processed twice | No duplicate frames are added | REQ-8 |
| Consecutive frames are nearly identical | Kept frames are at least one second apart | REQ-8 |
| N/A — permission: the user confirms the rights to the videos they supply | — | REQ-8 |
| Someone stages all files in git | Image and video files remain ignored | REQ-9 |
| N/A — concurrent: git exclusion rules involve no simultaneous actions | — | REQ-9 |
| No candidate images exist | Page shows an empty state naming the collection command | REQ-10 |
| An image cannot be loaded | Marked unreadable; other images stay usable | REQ-10 |
| Click falls outside the image | Ignored; the requested point does not change | REQ-11 |
| Definition file is missing or invalid | Interface does not start and names the problem | REQ-11 |
| Saving fails | Stays on the image, shows an error, does not advance | REQ-12 |
| Last pending image is completed | Shows completion and remaining skipped count | REQ-12 |
| Undo with no points placed | Nothing changes | REQ-13 |
| Skipped or rejected status | Skipped images return later; rejected ones leave export; both can be changed | REQ-13 |
| Image shows a soprano, several saxophones or no saxophone | User rejects it | REQ-13 |
| Every point is marked not visible | Cannot be saved; user is asked to reject the image | REQ-14 |
| Only the bell centre is not visible | Saved as not visible, other points kept | REQ-14 |
| Server stops with a partly marked image | Partial points are discarded; image stays pending | REQ-15 |
| Same image is open in two tabs | The last save wins | REQ-15 |
| No annotated images exist | Export stops with a clear error | REQ-16 |
| Frames come from the same video | All stay in the same split | REQ-16 |
| Annotated image file is missing | Excluded from export and reported | REQ-16 |
| Export has fewer images than the target | Proceeds with a warning showing current counts | REQ-17 |
| Enough total images but too few user frames | Warning names the missing user frames | REQ-17 |
| Exported dataset is missing | Trial stops and names the export command | REQ-18 |
| Apple GPU fails during training | Falls back to CPU with a visible notice | REQ-18 |
| Model finds no points in an image | Image is labelled as no detection, without error | REQ-19 |
| Trial output is regenerated | Annotations and manifest are never changed | REQ-19 |

## Out of Scope

- **Full training and evaluation on an unseen video** — this feature only proves the data is usable; quality is judged next.
- **Real-time tracking in the browser** — depends on a model that has passed evaluation.
- **Microphone input and animations** — they build on the tracked point, so they come later.
- **Datasets for other instruments** — saxophone comes first; only the point definition stays editable now.
- **Roboflow and generic web image search** — their image licenses cannot be verified to the required standard.
- **Soprano saxophones** — their straight shape differs from the tenor and alto chosen for training.
- **Images with more than one saxophone** — partly marked images would teach the model wrongly, so they are rejected.
- **Hosted or remote annotation** — the interface is local, and contributors run it from their own clone.
