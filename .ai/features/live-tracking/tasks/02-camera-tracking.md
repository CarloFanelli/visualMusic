# Task 02: camera-tracking

## Objective

The user chooses a camera and sees it live with the confident **tracked points** of the saxophone drawn on it, until pressing stop.

## Context

**Satisfies**: REQ-1, REQ-2, REQ-5, REQ-6, REQ-7

This is the core loop every later task builds on. REQ-1 appears again because only here does tracking exist for a second tab to collide with.

## Depends on

- Task 01

## Expected Behavior

- The page lists the cameras on this computer and starts tracking the chosen one.
- The camera image is mirrored, and each tracked point is drawn at its matching position.
- Points with confidence below 50% are not drawn; exactly 50% is drawn.
- Stop turns the camera off and returns to the source choice.
- No image or point is saved or sent outside this computer.

## Acceptance Criteria

- [ ] Any camera found can be chosen and tracked (REQ-2)
- [ ] Tracked points stay aligned on a mirrored image, also after resizing the window (REQ-6)
- [ ] A point below 50% is hidden, and one at exactly 50% is drawn (REQ-7)
- [ ] Stop turns the camera off and returns to the source choice (REQ-5)
- [ ] A second tab says tracking is open elsewhere while the first continues (REQ-1)
- [ ] With the real model and a 1080p camera: at least 20 updates per second, and 95% of images drawn within 150 ms (REQ-6)

## Edge Cases

- Page opened in a second tab during tracking → the second tab says tracking is open elsewhere; the first continues (REQ-1)
- Program stops during tracking → the page says the connection was lost and how to restart (REQ-1)
- No camera found → the camera choice is disabled with an explanation; video remains available (REQ-2)
- Camera permission refused → the page explains how to grant it; video remains available (REQ-2)
- Camera in use by another app or disconnected during tracking → tracking stops with a message and returns to the source choice (REQ-2)
- Camera image → shown mirrored, like looking in a mirror, with the points still aligned (REQ-6)
- Stop pressed twice, or while still starting → handled once; the camera ends up off (REQ-5)
- Tab closed without pressing stop → the program is ready for a new start and the camera is off (REQ-5)
- Window resized → points stay aligned; the image is never stretched (REQ-6)
- Two saxophones in the image → only the one the model is most confident about is tracked (REQ-6)
- Confidence exactly 50% → the point is drawn (REQ-7)

## Notes from implementation

- **Known limitation**: the speed targets were measured with the real model and Chrome's simulated 1080p camera, not a physical camera, which adds its own capture delay. They must be confirmed on the Mac's camera. /dev, 2026-11-09.
