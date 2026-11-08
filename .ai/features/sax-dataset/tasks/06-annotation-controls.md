# Task 06: annotation-controls

## Objective

The user can correct a mistake, postpone or discard an image, and mark a hidden point as not visible, so every image reaches a clear outcome.

## Context

**Satisfies**: REQ-13, REQ-14

This is also where tenor and alto selection happens: the user rejects sopranos, images with several saxophones and images with no saxophone. Not-visible points let partly hidden instruments still teach the model.

## Depends on

- Task 05

## Expected Behavior

- The user can undo the last placed point.
- The user can skip an image for later or reject it as unsuitable, and can change either status afterwards.
- The user can mark the requested point as not visible and move to the next point.

## Acceptance Criteria

- [ ] Undo removes only the last placed point and requests it again (REQ-13)
- [ ] A skipped image leaves the pending flow and returns after pending images are finished (REQ-13)
- [ ] A rejected image stays rejected after a restart, and the user can restore it (REQ-13)
- [ ] Marking a point as not visible saves it as not visible, with no position (REQ-14)

## Edge Cases

- Undo with no points placed → nothing changes (REQ-13)
- Skipped or rejected status → skipped images return later; rejected ones leave export; both can be changed (REQ-13)
- Image shows a soprano, several saxophones or no saxophone → the user rejects it (REQ-13)
- Every point is marked not visible → cannot be saved; the user is asked to reject the image (REQ-14)
- Only the bell centre is not visible → saved as not visible, other points kept (REQ-14)

## Notes from implementation

- **REQ-13 / AC 2 — divergence**: skipped images do not reopen by themselves. When pending images run out, the page shows the skipped count and a button to resume them, which keeps both this task's "returns later" and the completion message of the annotation flow. /dev, 2026-11-08.
- **Known limitation**: skipping or rejecting an image that already has saved points replaces those points, and restoring it does not bring them back. The loss is one image's clicks, and it avoids keeping points on images excluded from export. /dev, 2026-11-08.
- **New dependency**: Playwright is added for development only, in `requirements-dev.txt`, so the page's click flows are tested in the repository using the installed Chrome. `scripts/setup.sh` does not install it, and the tests are skipped without it. Agreed in /dev, 2026-11-08.
