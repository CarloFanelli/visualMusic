# Task 04: video-source

## Objective

The user chooses a video file and watches it at normal speed with the same tracking, able to pause and restart, so the model can be judged on an unseen video.

## Context

**Satisfies**: REQ-3, REQ-4

It reuses everything built for the camera, so it comes last. It also provides the repeatable test on the unseen video that the project still lacks.

## Depends on

- Task 03

## Expected Behavior

- The user picks a file from this computer, and it plays without being mirrored, with tracked points and the sound point on it.
- Pause freezes image and points; restart goes back to the beginning.
- If analysis is slower than the video, some images are not analysed, and the video keeps normal speed.
- A file that cannot be read shows an error and returns to the source choice.

## Acceptance Criteria

- [ ] A video file from this computer plays with tracked points aligned (REQ-3)
- [ ] The video keeps normal speed even when analysis is slower (REQ-4)
- [ ] Pause freezes image and points without advancing the 0.2-second timers (REQ-4)
- [ ] Restart returns to the beginning without carrying points over from the previous position (REQ-4)
- [ ] A file that is not a video shows an error and returns to the source choice (REQ-3)

## Edge Cases

- No file chosen → nothing starts and the source choice stays (REQ-3)
- Very long or large file → plays normally, because nothing is kept in memory beyond the current images (REQ-3)
- File is not a video, or damaged at the start → error, back to source choice (REQ-3)
- File damaged partway → stops at the last good image with a message; restart remains available (REQ-3)
- Analysis slower than the video → the video keeps normal speed and skips analysing some images (REQ-4)
- Video ends → the last image stays, with restart available (REQ-4)
- Pause → image and points freeze; the 0.2-second timers do not advance (REQ-4)
- Vertical video → points stay aligned; the image is never stretched (REQ-6)
