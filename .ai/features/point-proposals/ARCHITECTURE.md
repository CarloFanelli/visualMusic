---
feature: point-proposals
spec-version: 1.0
status: approved
---

# Architecture Plan: Point Proposals

## Technical Approach

### Overview

Two new commands sit beside the existing trial: one trains and publishes a model file, the other writes one proposal file per image. The annotation server stays free of the model and of heavy imports, and only serves those files. The page gains a review mode beside today's click mode, so hand marking stays unchanged. Annotations keep their format, so export needs no change. No new packages.

### Shared Concerns

#### Atomic local files

- **Appears in**: Task 01, Task 02, Task 03
- **Reference example**: `dataset_tools/annotations.py:61`
- **Rule**: Model and proposal files are replaced only through `atomic_writer`, so a failure or interruption leaves the earlier file intact.

## Per-Task Technical Guidance

### Task 01: full-training

**Files to modify:**
- `dataset_tools/trial.py` — make the training helpers take epochs and run name, so both commands share the GPU fallback.
- `dataset_tools/paths.py` — add the latest model location under `RUNS`.
- `README.md` — document the command.
- `tests/test_trial.py` — keep the short-training assertion passing.

**Files to create:**
- `dataset_tools/train.py` — command; structure like `dataset_tools/trial.py:74` and `:96`.
- `tests/test_train.py` — mirror the `FakeModel` in `tests/test_trial.py:36`.

**Key decisions:**
- Each training starts from the base weights in `trial.WEIGHTS`, so old mistakes do not accumulate.
- Publish by copying `best` to a fixed file only after training returns; a separate run folder may be overwritten freely.

**Watch out for:**
- Interrupting with Ctrl+C raises `KeyboardInterrupt`, which `trial.py:99` does not catch — dataset_tools/train.py → publish only after training returns; test: a failing model leaves the old file byte-identical.

---

### Task 02: proposal-generation

**Files to modify:**
- `dataset_tools/paths.py` — add `PROPOSALS` under `data/`.
- `.gitignore` — ignore it; add a case to `tests/test_gitignore.py:14`.
- `README.md` — document the command.

**Files to create:**
- `dataset_tools/proposals.py` — command plus load and save of one proposal; storage like `dataset_tools/annotations.py:23` and `:75`.
- `tests/test_proposals.py` — fake model as in `tests/test_trial.py:20`.

**Patterns to reuse:**
- Device choice as in `dataset_tools/trial.py:77`; best detection as in `:65`; detection check `has_detection` at `:50`.

**Key decisions:**
- A proposal stores points in annotation shape, so `annotations.validate` checks it.
- Clip normalized coordinates to 0–1 here.
- Cover pending and skipped images; leave other proposal files alone.

**Watch out for:**
- A collection may be appending to the manifest — `dataset_tools/manifest.py:23` → load with `repair=False`; test: a torn last line stays in the file.
- Manifest paths are untrusted — `dataset_tools/export.py:115` → apply the same plain-name check and count as unreadable; test: `../x.jpg` is not read.
- An undecodable file only warns and yields no image — `ultralytics/data/loaders.py:509` → treat an empty result or read error as unreadable; test: a corrupt file with a real model call.
- `keypoints.xyn` can exceed the image — `ultralytics/engine/results.py` xyn divides without clipping → clip; test: 1.02 is stored as 1.0.

---

### Task 03: confirm-proposals

**Files to modify:**
- `dataset_tools/annotate/server.py` — add the proposals folder to `Storage` (`:23`), `has_proposal` to `_state` (`:72`), and a read route beside `_send_annotation` (`:91`, `:106`).
- `dataset_tools/annotate/static/index.html` — review mode: load the proposal in `openImage` (`:230`), order in `nextPending` (`:121`), counts in `renderProgress` (`:130`), Conferma and Enter.
- `tests/test_annotate_server.py`, `tests/e2e/test_annotation_page.py` — fixtures pass a temporary proposals folder.
- `README.md` — describe the new flow.

**Patterns to reuse:**
- Late-response guard at `index.html:247`; save and retry through `store` (`:266`).
- Validate each proposal with `annotations.validate` (`dataset_tools/annotations.py:36`); invalid means no proposal.

**Key decisions:**
- `has_proposal` depends only on a valid file, not on status, so a restored image regains it.
- Hide Annulla and Punto non visibile in review mode until Task 04.

**Watch out for:**
- A default proposals folder would make tests read real data — `tests/test_annotate_server.py:24`, `tests/e2e/test_annotation_page.py:32` → pass a temporary folder; test: fixtures assert it is under `tmp_path`.
- The browser keeps the old image while the next loads — `index.html:310` → start the 300 ms from the photo `load` event and proposal arrival; test: double Enter saves one image.
- Enter on a focused button also clicks it — `index.html:341` → handle Enter on `document`, ignore `event.repeat`, always `preventDefault`; test: focus Non adatta, press Enter, status stays annotated.
- A click in review mode must not reach the hand-click handler — `index.html:315` → check the mode first; test: click leaves points unchanged.

---

### Task 04: correct-points

**Files to modify:**
- `dataset_tools/annotate/static/index.html` — draggable markers (they have `pointer-events: none` at `:39`), point list, selection, hide and undo history; `openImage` (`:244`) enters review mode for annotated images.
- `tests/e2e/test_annotation_page.py` — change tests that redo points by clicks on a reopened image (`:186`, `:210`).
- `.ai/memory/dataset.md` — replace the decision "A reopened image is marked again in full".
- `README.md` — describe moving points.

**Patterns to reuse:**
- Normalized coordinates from `photo.getBoundingClientRect` as at `index.html:317`.

**Key decisions:**
- Clamp the position to 0–1 while dragging, and use pointer capture so the drag survives leaving the image.
- Undo keeps a snapshot per change.

**Watch out for:**
- A hidden point keeping `x`/`y` is refused with an error — `dataset_tools/annotations.py:53` → remove them on hide; test: hide, confirm, stored point has only name and visible.
- Moving a saved point must leave the file until confirm — `index.html:186` `.marker.saved` flow → edit a copy; test: move, reopen, old position remains.
- Moving after a failed save would retry stale points — `index.html:269` captures the body → rebuild it on retry; test: fail, move, retry stores the new position.
