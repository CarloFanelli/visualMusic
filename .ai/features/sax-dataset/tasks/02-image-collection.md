# Task 02: image-collection

## Objective

The user can run one command that gathers candidate saxophone images from three open sources, keeps only safely licensed ones, and records the proof of each license.

## Context

**Satisfies**: REQ-3, REQ-4, REQ-5, REQ-6

This creates the manifest, the license proof that every later task reads. The filter is strict because the user allows only images free of copyright problems. Tenor and alto selection happens later, by rejecting images during annotation.

## Depends on

- Task 01

## Expected Behavior

- The command collects candidates from Wikimedia Commons, Open Images and Openverse, then prints kept and rejected counts per source, with rejections grouped by reason.
- Only CC0, public domain and CC BY images are kept.
- Every kept image has a manifest record with source URL, author, license, license URL, collection date and file fingerprint.
- Running the command again adds only new images and leaves existing records unchanged.

## Acceptance Criteria

- [ ] One command collects candidates from all three sources (REQ-3)
- [ ] Each allowed license family is kept; CC BY-SA, NC, ND, GPL, GFDL and unknown licenses are rejected and counted (REQ-4)
- [ ] Every kept image has a complete manifest record, and no record exists without its file (REQ-5)
- [ ] A second run leaves earlier manifest records byte-identical and adds no duplicates (REQ-6)

## Edge Cases

- One source is unreachable → collection continues with the others and names the failed source (REQ-3)
- A source asks to slow down → collection waits as requested and retries; it never bypasses the limit (REQ-3)
- A source returns no results → reports zero for that source and continues (REQ-3)
- License is missing or unrecognised, such as GPL or GFDL → the image is rejected and counted by reason (REQ-4)
- License is CC BY-SA, NC or ND → the image is rejected and counted by reason (REQ-4)
- CC BY image has no identifiable author → the image is rejected, since attribution cannot be kept (REQ-5)
- Download fails → no manifest record is created for that image (REQ-5)
- Same image is found in two sources → kept once, detected by file fingerprint (REQ-6)
- Collection is interrupted → re-running continues without duplicates (REQ-6)

## Notes from implementation

- **REQ-5 / AC 3 — divergence**: the spec requires an author and a license URL on every record, but CC0 and public domain images may have neither. Such images store author `unknown`, and a Commons public domain image without a license URL points to its file page, which holds the license statement. CC BY images without an author stay rejected. /dev, 2026-11-08.
- **Known limitation**: Openverse filters disallowed licenses itself, so they are not in its rejection counts, and anonymous searches stop at 240 results. The report states both. /dev, 2026-11-08.
- **Known limitation**: Commons categories and open searches also return images with no visible saxophone, such as an album page. The user rejects them during annotation (Task 06). /dev, 2026-11-08.
- **Impacts Task 04**: `dataset_tools/images.py` holds the atomic download, and each manifest record stores `download_url`, `sha256` and `file`.
