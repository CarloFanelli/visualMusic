# Task 01: training-environment

## Objective

The user can install the training environment with one documented command, check that it works on their Mac, and rely on image and video files staying out of git.

## Context

**Satisfies**: REQ-1, REQ-2, REQ-9

Every later task runs inside this environment and stores data under the rules set here, so it comes first.

## Depends on

None

## Expected Behavior

- One documented command creates an environment isolated from the system Python and installs what training needs.
- An environment check prints the installed YOLO version and whether Apple GPU acceleration is available.
- Image and video files under the project's data area are ignored by git, while the manifest and annotations can be committed.

## Acceptance Criteria

- [ ] On a clean checkout, the documented command finishes with a working environment and leaves the system Python untouched (REQ-1)
- [ ] The check prints the YOLO version and the Apple GPU availability (REQ-2)
- [ ] Staging all files leaves image and video files unstaged, while the manifest and annotation paths stay stageable (REQ-9)

## Edge Cases

- Setup is run a second time → reuses the environment and ends successfully (REQ-1)
- Network drops during installation → stops with a clear error; re-running completes the install (REQ-1)
- Apple GPU is unavailable → the check reports CPU-only with a warning, without failing (REQ-2)
- Environment is not installed → the check tells the user to run setup (REQ-2)
- Someone stages all files in git → image and video files remain ignored (REQ-9)
- N/A — concurrent: git exclusion rules involve no simultaneous actions (REQ-9)
