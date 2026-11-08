---
feature: sax-dataset
spec-version: 1.0
status: approved
---

# Architecture Plan: Sax Dataset

## Technical Approach

### Overview

The repository holds no code yet, so this feature sets the layout: a Python 3.11 package, `dataset_tools/`, with one runnable module per command, and versioned data files under `data/`. The only direct runtime dependency is `ultralytics==8.4.208`, whose declared dependencies already bring OpenCV, Pillow, requests and torch; `pytest` is added for tests. FFmpeg is not installed and not needed. The annotation interface uses the standard-library HTTP server and one static page, with no web framework or build step. References to Ultralytics were read from its current `main` source; `/dev` confirms them against the installed 8.4.208.

### Shared Concerns

#### Data contract

- **Appears in**: Task 02, Task 03, Task 04, Task 05, Task 06, Task 07
- **Reference example**: `dataset_tools/paths.py`, `dataset_tools/manifest.py`
- **Rule**: `data/manifest.jsonl` is append-only, one record per image with a stable `image_id`. `data/annotations/{image_id}.json` holds status and points as coordinates normalized against the upright image. All paths come from `paths.py`.
- **Watch out for**: Annotations store normalized coordinates, so previews and originals share them only if both are upright.

#### Instrument definition

- **Appears in**: Task 05, Task 06, Task 07
- **Reference example**: `instruments/saxophone.json`
- **Rule**: Holds class name, ordered point names and mirror pairs. Order: bell centre, bell edge left, bell edge right, mouthpiece; left and right mean as seen in the image.

## Per-Task Technical Guidance

### Task 01: training-environment

**Files to create:**
- `requirements.txt` — pins `ultralytics==8.4.208` and `pytest`.
- `scripts/setup.sh` — creates `.venv` and installs; safe to re-run; stops on the first error.
- `dataset_tools/check_env.py` — prints YOLO version and Apple GPU availability; pattern for the other commands.
- `dataset_tools/paths.py` — single source for data locations.
- `.gitignore` — ignores `.venv/`, `data/images/`, `data/videos/`, `data/previews/`, `data/cache/`, `data/export/`, `runs/`, and model weights.
- `README.md` — documents setup and every command, and the AGPL-3.0 consequence.
- `tests/test_gitignore.py` — proves the REQ-9 rules with `git check-ignore`.

**Key decisions:**
- Directory rules, not extension rules: a future image format stays ignored, and manifest and annotations stay committable.
- The check runs through `.venv/bin/python`; `setup.sh` prints that command.

### Task 02: image-collection

**Files to create:**
- `dataset_tools/manifest.py` — read and append records; defines the Data contract.
- `dataset_tools/licenses.py` — allowlist mapping source license values to `cc0`, `public-domain`, `cc-by`, or a rejection reason.
- `dataset_tools/sources/commons.py` — categories `Tenor saxophones` and `Alto saxophones`, plus one subcategory level; JPEG and PNG only.
- `dataset_tools/sources/open_images.py` — class `/m/06ncr`; metadata from the Open Images CSVs, files from the `open-images-dataset` S3 mirror.
- `dataset_tools/sources/openverse.py` — queries tenor and alto, with `license=by,cc0,pdm`.
- `dataset_tools/collect.py` — orchestrates and prints the report.
- `tests/test_licenses.py`, `tests/test_manifest.py` — with recorded source responses, no network.

**Key decisions:**
- Rejection works by allowlist, so the Commons value `Attribution` falls to unknown.
- `image_id` is source plus source key; fingerprint is SHA-256 of the downloaded bytes.
- Save the file by atomic rename, then append its record.

**Watch out for:**
- Commons `Artist` is HTML and categories include audio — `dataset_tools/sources/commons.py` → strip markup, filter by MIME; test: linked author and `.ogg` member.
- Openverse rejects anonymous requests past 240 results — `dataset_tools/sources/openverse.py` → stop at the cap and report it; test: recorded error response ends cleanly.
- Openverse filtering hides rejected licenses from counts — `dataset_tools/collect.py` → report they are filtered at source, still apply the allowlist; test: a returned `by-sa` record is rejected.
- Commons answered HTTP 429 during research — `dataset_tools/sources/commons.py` → sequential requests, honour `Retry-After`, identifying user agent; test: recorded 429 retries once after waiting.
- Interrupted append can leave a torn final line — `dataset_tools/manifest.py` → ignore and repair only a malformed last line; test: truncated file loads, earlier bytes unchanged.
- Open Images train metadata is about 2 GB and slow — `dataset_tools/sources/open_images.py` → stream it and cache filtered rows in `data/cache/`; test: second run performs no CSV download.

### Task 03: video-frames

**Files to create:**
- `dataset_tools/frames.py` — reads `data/videos/`, writes JPEG frames to `data/images/`, appends user-owned records.
- `tests/test_frames.py` — uses a tiny video generated in the test.

**Patterns to reuse:**
- Data contract (see Shared Concerns).
- Report style of `dataset_tools/collect.py`.

**Key decisions:**
- OpenCV reads the video, because Ultralytics already installs it and FFmpeg is absent.
- `video_id` is a hash of the video's bytes, so renaming a video creates no duplicates.
- `image_id` combines `video_id` and timestamp; frames are taken every second.
- The manifest `license` value is `user-owned`, and `video_id` is the grouping key Task 07 uses.

**Watch out for:**
- Phone videos may decode sideways, misleading annotation — `dataset_tools/frames.py` → verify orientation on a portrait clip before bulk extraction; test: portrait fixture produces upright frames.

### Task 04: image-restore

**Files to create:**
- `dataset_tools/restore.py` — downloads missing or mismatched online-sourced files and prints the three counts.
- `tests/test_restore.py` — uses a local stub for downloads.

**Patterns to reuse:**
- Atomic-save download from Task 02, moved into `dataset_tools/manifest.py` or a small shared helper; polite retry behaviour from `dataset_tools/sources/commons.py`.

**Key decisions:**
- Each manifest record stores its `download_url`, separate from the human source page, so restore needs no source query.
- Restore never edits the manifest: "missing" is a run result, recomputed each time.

### Task 05: annotation-flow

**Files to create:**
- `instruments/saxophone.json` — Instrument definition (see Shared Concerns).
- `dataset_tools/instrument.py` — loads and validates the definition, including mirror pairs.
- `dataset_tools/annotations.py` — load, validate and atomically save annotations.
- `dataset_tools/annotate/server.py` — standard-library server bound to `127.0.0.1`.
- `dataset_tools/annotate/static/index.html` — list, image, click flow; no build step.
- `tests/test_annotations.py`, `tests/test_annotate_server.py`.

**Key decisions:**
- The server creates cached upright previews, at most 1600 pixels on the long side, in `data/previews/`, and the page preloads the next one, to meet the 500 ms target with large originals.
- Partial points live only in the page, so a stopped server discards them.

**Watch out for:**
- Local server can be called by any open website — `dataset_tools/annotate/server.py` → reject unexpected `Host` and `Origin` headers; test: foreign `Origin` cannot save.
- Crafted image ids could read or write outside data folders — `dataset_tools/annotate/server.py` → accept only ids in the manifest; test: `../` id is refused.
- Crash mid-save could corrupt an annotation — `dataset_tools/annotations.py` → temporary file plus `os.replace`; test: failed write leaves the previous file intact.
- Browser and Ultralytics must agree on orientation — `ultralytics/data/utils.py:544` reads upright → previews apply EXIF orientation; test: EXIF-rotated fixture keeps normalized points on target.

### Task 06: annotation-controls

**Files to modify:**
- `dataset_tools/annotate/static/index.html` — undo, skip, reject, restore and not-visible controls.
- `dataset_tools/annotate/server.py` — status changes.
- `dataset_tools/annotations.py` — validation for status and visibility.
- `tests/test_annotations.py`, `tests/test_annotate_server.py` — new cases.

**Patterns to reuse:**
- Atomic save and origin checks from Task 05.

**Key decisions:**
- Skipped and rejected are stored annotation statuses, so they survive restarts and travel through git.
- A not-visible point is stored with `visible: false` and no coordinates.
- The all-not-visible rule is enforced on the server too, so the page is not the only guard.

### Task 07: dataset-export

**Files to create:**
- `dataset_tools/export.py` — rebuilds `data/export/` with images, labels and `data.yaml`; prints target counts.
- `tests/test_export.py`.

**Key decisions:**
- Labels use `kpt_shape: [4, 3]`: visible is 2, not visible is `0 0 0`, excluded from keypoint loss (`ultralytics/utils/loss.py:833`).
- `flip_idx` is `[0, 2, 1, 3]`, derived from the mirror pairs.
- Split is a stable hash of the group key: `video_id` for frames, `image_id` otherwise, about 20% validation.
- The box wraps visible points with 10% padding, at least 5% of the image, clamped to it.
- Images are copied, so the export is self-contained and training writes nothing beside the originals.

**Watch out for:**
- A missing `flip_idx` silently disables flip augmentation — `ultralytics/data/augment.py:2900` → always write it; test: generated YAML length equals point count.
- Few videos can leave one split empty — `dataset_tools/export.py` → stop with a clear error if a split is empty; test: single-group dataset.
- Out-of-range values fail label checks — `ultralytics/data/utils.py:483` → clamp boxes; test: point on the image corner exports valid.

### Task 08: trial-training

**Files to create:**
- `dataset_tools/trial.py` — trains briefly on `data/export/data.yaml`, writes to `runs/trial/`, then draws predictions on validation images.
- `tests/test_trial.py` — covers the missing dataset and the no-detection labelling, without real training.

**Key decisions:**
- Smallest YOLO26 pose weights, 10 epochs, image size 640, Apple GPU first; tune only if the 30-minute target is missed.
- Predictions are drawn by this module, so an image with no detection gets an explicit label.
- Weights download on first run, so it needs network access.

**Watch out for:**
- Apple GPU pose was buggy historically, and wrong results raise no error; Ultralytics issue #4031 is closed — `dataset_tools/trial.py` → a CPU fallback covers exceptions only, so the drawn images must be inspected; test: simulated device failure switches to CPU.
