# Task 07: dataset-export

## Objective

The user can turn finished annotations into a YOLO keypoint dataset with training and validation splits, and see how far it is from the 300-image target.

## Context

**Satisfies**: REQ-16, REQ-17

This converts the user's work into what training reads. Export can run at any time, so the pipeline can be proven before all images are annotated. The target itself is reached through the user's annotation work, not by code.

## Depends on

- Task 05
- Task 06

## Expected Behavior

- The command builds training and validation splits from annotated images only, leaving out skipped, rejected and pending ones.
- The object box each model example requires is derived automatically from the visible points.
- The command prints the total annotated images and user-video frames against the targets of 300 and 50.

## Acceptance Criteria

- [ ] Export contains annotated images only, in training and validation splits, in a form YOLO keypoint training accepts (REQ-16)
- [ ] Each exported example has an object box derived from its visible points, with no extra user input (REQ-16)
- [ ] Not-visible points are exported as not visible (REQ-16)
- [ ] The summary reports counts against the targets of 300 annotated images and 50 user-video frames (REQ-17)

## Edge Cases

- No annotated images exist → export stops with a clear error (REQ-16)
- Frames come from the same video → all stay in the same split (REQ-16)
- Annotated image file is missing → excluded from export and reported (REQ-16)
- Annotation's points no longer match the definition → excluded from export and reported (REQ-11 · from code)
- Export has fewer images than the target → proceeds with a warning showing current counts (REQ-17)
- Enough total images but too few user frames → the warning names the missing user frames (REQ-17)

## Notes from implementation

- **Impacts Task 08**: the dataset is at `data/export/data.yaml` and validation images are in `data/export/images/val/`. Export can stop with an error when one split is empty, which is likely with very few images or videos.
