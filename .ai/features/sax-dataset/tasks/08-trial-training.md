# Task 08: trial-training

## Objective

The user can run a short training on the exported dataset and look at validation images with predicted points, proving that the data and environment work end to end.

## Context

**Satisfies**: REQ-18, REQ-19

This closes the feature. It proves the pipeline works, not that the model is good: quality is judged in a later feature on an unseen video.

## Depends on

- Task 07

## Expected Behavior

- The command trains briefly on the exported dataset and saves a model file, finishing within 30 minutes on the M1 Pro.
- It then produces validation images with predicted points drawn on them and prints where they are.

## Acceptance Criteria

- [ ] A trial training completes on the exported dataset and saves a model file (REQ-18)
- [ ] The trial finishes within 30 minutes on the M1 Pro (REQ-18)
- [ ] Validation images with predicted points drawn on them are produced (REQ-19)

## Edge Cases

- Exported dataset is missing → the trial stops and names the export command (REQ-18)
- Apple GPU fails during training → falls back to CPU with a visible notice (REQ-18)
- Model finds no points in an image → the image is labelled as no detection, without error (REQ-19)
- Trial output is regenerated → annotations and manifest are never changed (REQ-19)

## Notes from implementation

- **Known limitation**: the 30-minute target is not yet measured on a full dataset. A real run on 13 training and 4 validation images took 80 seconds on the Apple GPU, with about 58 seconds of training. Scaling by image count suggests roughly 18 minutes for 240 training images, an estimate only. Measure it on the real dataset. /dev, 2026-11-08.
- **Known limitation**: Ultralytics sends anonymous usage events during training while its `sync` setting is on, its default. The code sends no images, but this project leaves the setting unchanged. The user can run `.venv/bin/yolo settings sync=False`. /dev, 2026-11-08.
