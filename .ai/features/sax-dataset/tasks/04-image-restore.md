# Task 04: image-restore

## Objective

The user, or a future contributor on a fresh clone, can bring back missing online-sourced image files from the manifest and resume annotation.

## Context

**Satisfies**: REQ-7

Image files stay out of git, so a fresh clone holds only the manifest and annotations. This task makes that versioned data enough to continue working.

## Depends on

- Task 02
- Task 03

## Expected Behavior

- The command downloads every missing online-sourced image listed in the manifest and prints restored, missing and user-owned counts.
- A restored file is used only if it matches its recorded fingerprint.

## Acceptance Criteria

- [ ] On a fresh clone, the command restores online-sourced images that are still available (REQ-7)
- [ ] Files already present and valid are not downloaded again (REQ-7)
- [ ] A restored file that fails the fingerprint check is not kept (REQ-7)

## Edge Cases

- Source has removed an image → reported as missing and left out of export; its annotation is kept (REQ-7)
- Restored file differs from its fingerprint → treated as missing and not used (REQ-7)
- User-owned frame is missing → reported as restorable only from the user's video (REQ-7)
