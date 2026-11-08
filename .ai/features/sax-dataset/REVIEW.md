---
feature: sax-dataset
status: APPROVED
reviewed: 2026-11-08
head: bb62c9d857304be934de85778799bbb92ce5da4e
---

# Review — sax-dataset

**Scope**: 18 files (delta since review head `c0e8ae5e`, plus the files of addressed findings; 1 workflow artifact under `.ai/` excluded)
**Findings**: 0 must-fix · 0 should-fix · 0 nit

## Findings

### F-1 · must-fix · bug · spaced license names pass as plain CC BY   [ADDRESSED]
**File**: `dataset_tools/licenses.py:45-46`
**Issue**: The `cc by` fallback classifies only the second word, so `CC BY SA 4.0`, `CC BY NC 4.0`, `CC BY ND 4.0` and `CC BY 4.0 NC` all return `cc-by` and are kept.
**Change**: Pass the second word to `_classify_cc_terms` only when it contains a hyphen and return `unrecognised` otherwise, so the `_CC_BY_NAME` pattern stays the only way to plain CC BY, and add these four values to `tests/test_licenses.py`.
**Why**: REQ-4 keeps only CC0, public domain and CC BY, and the allowlist must reject anything it does not recognise. Confirmed by calling `classify` on each value.

### F-2 · must-fix · bug · images are kept without source or license URL   [ADDRESSED]
**File**: `dataset_tools/collect.py:36-47`
**Issue**: `rejection_reason` checks the author and the download URL but not `source_url` or `license_url`, so an Openverse result with an empty landing page or a null license URL is kept with an incomplete attribution record.
**Change**: Reject a candidate with an empty `source_url` as `no-source-url`, and a CC BY candidate with an empty `license_url` as `no-license-url`, each with a test in `tests/test_collect.py`.
**Why**: REQ-5 requires both fields on every record, and the note in task 02 exempts only CC0 and public domain images. A live sample of 20 Openverse results had none empty, so this guards a gap in the code rather than an observed record.

### F-3 · must-fix · bug · clicks register while the next image is loading   [ADDRESSED]
**File**: `dataset_tools/annotate/static/index.html:307-311`
**Issue**: `openImage` assigns the new image and asks for its first point at once, while the browser keeps showing the previous image until the new one loads, so a click in that window saves a point chosen on the previous image to the new one.
**Change**: Add `&& elements.photo.complete` to `canPlacePoint`, which also refuses the zero-size box that turns a first click into `NaN`.
**Why**: Nothing reports the wrong point, so it silently damages the dataset. The window is widest when a preview must be generated and the preload has not finished. Established by reading the code and the browser's image-loading rules; not reproduced, because this review ran no browser.

### F-4 · must-fix · bug · export errors hide missing and outdated images   [ADDRESSED]
**File**: `dataset_tools/export.py:123-127`
**Issue**: When selection leaves no images or only one split, `ExportError` is raised and `main` prints only its message, so a fresh clone with annotations but no image files is told `No annotated images to export.` and never learns that the files are missing.
**Change**: Include `report.lines()` in both `ExportError` messages, and add a test in `tests/test_export.py` with an annotated image whose file is missing.
**Why**: The spec requires a missing annotated image to be excluded and reported, under REQ-16. Confirmed by running `export` on that case.

### F-5 · should-fix · bug · one malformed annotation file stops the whole page   [ADDRESSED]
**File**: `dataset_tools/annotations.py:36-52`
**Issue**: `validate` raises `TypeError` on an unhashable status and `AttributeError` on a non-object point, and `status_of` catches only `InvalidAnnotation`, so one such versioned file makes `/api/state` fail and the page cannot load any image.
**Change**: Have `validate` raise `InvalidAnnotation` for a non-string status and for any point that is not an object, with cases in `tests/test_annotations.py`.
**Why**: `load` already treats an unusable file as absent, and annotations arrive through git from contributors. Confirmed by calling `status_of` on both values.

### F-6 · should-fix · bug · setup accepts a Python too old for the tools   [ADDRESSED]
**File**: `scripts/setup.sh:7`, `README.md:7`
**Issue**: The README asks only for Python 3 and setup uses whatever `python3` is, yet `dataset_tools/frames.py:24` and `dataset_tools/restore.py:32` call `hashlib.file_digest`, which needs 3.11, while `ultralytics` installs on 3.8 and later.
**Change**: Stop `setup.sh` with a clear message before creating `.venv` when `python3` is older than 3.11, and state 3.11 in the README.
**Why**: This Mac's `/usr/bin/python3` is 3.9.6, so a contributor on that interpreter would get a successful setup and an `AttributeError` later, when extracting frames or restoring images.

### F-7 · should-fix · security · restore trusts file paths from the versioned manifest   [ADDRESSED]
**File**: `dataset_tools/restore.py:50-56`
**Issue**: `images_dir / record["file"]` accepts an absolute or `../` value, and line 56 deletes that path when its fingerprint differs, so a bad manifest line from a contributor can delete a file outside the images folder.
**Change**: Treat a record as missing, without touching the disk, when `Path(record["file"]).name != record["file"]`, and add a case to `tests/test_restore.py`.

### F-8 · should-fix · convention · the page's click flow has no versioned test   [ADDRESSED]
**File**: `tests/test_annotate_server.py`
**Issue**: No test in the repository exercises the page logic of click order, automatic save and advance, undo, skip, reject, restore and not-visible points; these flows were checked only by browser scripts in a temporary folder that will disappear.
**Change**: Move those Playwright flows into `tests/e2e/`, listing Playwright as a development-only dependency and skipping the tests when it is absent.
**Why**: REQ-11 to REQ-14 state behavior a test can observe. Without these tests, the fix for F-3 cannot be protected against regression.

### F-9 · nit · bug · valid multi-picture JPEGs are rejected   [ADDRESSED]
**File**: `dataset_tools/images.py:6`
**Issue**: Pillow reports some camera JPEGs as `MPO`, which is missing from `EXTENSIONS`, so they count as `unsupported-format` although OpenCV reads them.
**Change**: Add `"MPO": "jpg"` to `EXTENSIONS`, with a generated test file.

### F-10 · nit · bug · invalid mirror pairs pass the definition check   [ADDRESSED]
**File**: `dataset_tools/instrument.py:32-34`
**Issue**: A pair naming one point twice, or a point used in two pairs, is accepted; the overlapping pairs tried here produced the invalid `flip_idx` `[0, 2, 3, 2]`, which would swap points wrongly in training.
**Change**: Raise `ValueError` when a pair's two names are equal or when a point appears in more than one pair.

### F-11 · nit · bug · a dataset error is reported as a GPU failure   [ADDRESSED]
**File**: `dataset_tools/trial.py:45`
**Issue**: Ultralytics raises `RuntimeError` for a bad dataset too (`ultralytics/engine/trainer.py:880`), so the notice blames the Apple GPU, training restarts on the CPU, and its second failure reaches the user as a raw traceback.
**Change**: Reword the notice to say training stopped on the GPU with the shown error, and catch `RuntimeError` in `main` to print `Trial stopped:` as it does for `TrialError`.

### F-12 · nit · bug · a failed trial leaves old predictions in place   [ADDRESSED]
**File**: `dataset_tools/trial.py:78-83`
**Issue**: The previous predictions are removed only after training succeeds, so after a failed run the folder still shows images from an earlier model.
**Change**: Move the removal of `predictions_dir` before the `_train` call.

### F-13 · nit · bug · an author ending in an unfinished entity is lost   [ADDRESSED]
**File**: `dataset_tools/sources/commons.py:24-26`
**Issue**: `author_from_html` never calls `parser.close()`, so plain text such as `AT&T` stays in the parser's buffer, the author becomes `None`, and a valid CC BY image is rejected as `no-author`.
**Change**: Call `parser.close()` after `parser.feed(...)`.

### F-14 · nit · bug · the last rate-limit wait is pointless   [ADDRESSED]
**File**: `dataset_tools/http_client.py:58-62`
**Issue**: After the fourth 429 the client still sleeps for the full `Retry-After`, up to the 600 seconds seen from this host, and then gives up.
**Change**: Skip the sleep on the last attempt.

### F-15 · nit · bug · restore can edit the manifest   [ADDRESSED]
**File**: `dataset_tools/restore.py:49`
**Issue**: `manifest.load` runs with its default repair, which truncates a torn last line, although the plan says restore never edits the manifest and a collection may be appending.
**Change**: Pass `repair=False`, as in `dataset_tools/export.py:107`.

### F-16 · nit · bug · leftover annotation temp files can be committed   [ADDRESSED]
**File**: `.gitignore:7-11`
**Issue**: A killed save can leave `data/annotations/.{image_id}.*.part` in the versioned folder, and `git add -A` would stage it.
**Change**: Add `data/annotations/*.part` to `.gitignore` and a case to `tests/test_gitignore.py`.

### F-17 · nit · convention · pytest is not pinned   [ADDRESSED]
**File**: `requirements.txt:2`
**Issue**: `pytest` has no version, while the plan pins it and `requirements.txt:1` pins `ultralytics`.
**Change**: Write `pytest==9.2.0`, the installed version.

### F-18 · nit · dup · atomic file writing is repeated   [ADDRESSED]
**File**: `dataset_tools/annotate/server.py:38-45`, `dataset_tools/annotations.py:59-67`
**Issue**: Both files repeat the same temporary-file, replace and clean-up sequence.
**Change**: Keep one context manager in `dataset_tools/annotations.py` and use it in both places.

### F-19 · should-fix · security · export trusts file paths from the versioned manifest   [ADDRESSED]
**File**: `dataset_tools/export.py:113`, `dataset_tools/export.py:146-147`
**Issue**: `_select` accepts a `file` value such as `../../../victim.jpg`, and `shutil.copyfile` then writes through that path, so a bad manifest line from a contributor overwrites a file outside the export folder.
**Change**: In `_select`, report a record as a missing file when `Path(record["file"]).name != record["file"]`, as `dataset_tools/restore.py:52` does, and add a case to `tests/test_export.py`.
**Why**: F-7 closed this gap only in restore. Confirmed by running `export` on such a record in the real folder layout: the file outside the export folder was overwritten and nothing was reported.
