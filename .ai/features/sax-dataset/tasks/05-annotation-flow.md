# Task 05: annotation-flow

## Objective

The user can open a local page, see all candidate images with their progress, click each point in order, and move on automatically without losing saved work.

## Context

**Satisfies**: REQ-10, REQ-11, REQ-12, REQ-15

This is the fast path the user asked for instead of a generic image viewer. Point names come from an editable file, so another instrument needs no code change. Undo, skip, reject and not-visible controls arrive in Task 06.

## Depends on

- Task 02

## Expected Behavior

- A page on localhost lists every candidate image with its status and overall progress.
- The page names the point to place next, in the order set by the instrument definition file, and each click places one point.
- After the last point the annotation saves automatically and the next pending image opens, within 500 ms on the M1 Pro.
- After a restart the page resumes at the first pending image; any saved image can be reopened and its points changed.
- The page is reachable only from the same computer and uploads no image anywhere.

## Acceptance Criteria

- [ ] The list shows each image's status and overall progress (REQ-10)
- [ ] Points are requested in definition-file order; editing that file changes the order and names without code changes (REQ-11)
- [ ] After the last point, the annotation is saved and the next pending image opens within 500 ms (REQ-12)
- [ ] After a restart, saved annotations remain and the page resumes at the first pending image (REQ-15)
- [ ] Reopening a saved image shows its points, and changed points replace the old ones (REQ-15)
- [ ] The page cannot be reached from another computer on the network (REQ-10)

## Edge Cases

- No candidate images exist → the page shows an empty state naming the collection command (REQ-10)
- An image cannot be loaded → marked unreadable; other images stay usable (REQ-10)
- Click falls outside the image → ignored; the requested point does not change (REQ-11)
- Definition file is missing or invalid → the interface does not start and names the problem (REQ-11)
- Definition points changed after annotating → affected images return to pending, and their old points stay stored until re-annotated (REQ-11 · from code)
- Saving fails → stays on the image, shows an error, does not advance (REQ-12)
- Last pending image is completed → shows completion and the remaining skipped count (REQ-12)
- Server stops with a partly marked image → partial points are discarded; the image stays pending (REQ-15)
- Same image is open in two tabs → the last save wins (REQ-15)

## Notes from implementation

- **REQ-11 / AC 2 — divergence**: each point in the definition file has a stable `name`, stored in annotations, and a `label`, shown to the user. Labels are Italian, as in the mockup the user chose; names are English, so changing a label does not send images back to pending. /dev, 2026-11-08.
- **REQ-15 / AC 5 — divergence**: a reopened image shows its saved points, and the first click starts a full new set that replaces them on save. Individual points cannot be moved one at a time. /dev, 2026-11-08.
- **Known limitation**: the unreadable status is only shown on the page and is recomputed in each session; it is not stored. /dev, 2026-11-08.
- **Impacts Task 06**: `annotations.validate` accepts only `annotated` and visible points today, and `status_of` drives the page list. The completion message already counts `skipped`.
- **Impacts Task 07**: use `annotations.status_of` to leave out annotations that no longer match the definition. `Instrument.mirror_pairs` holds the pairs for `flip_idx`, and point names are the keys, not labels.
