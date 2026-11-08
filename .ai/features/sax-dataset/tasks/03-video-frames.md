# Task 03: video-frames

## Objective

The user can turn their own saxophone videos into candidate images that appear alongside the collected ones.

## Context

**Satisfies**: REQ-8

The user's videos are the data closest to real use, and they carry no third-party license. Frames join the manifest created by Task 02, marked as user-owned.

## Depends on

- Task 02

## Expected Behavior

- The command reads the videos the user supplies and adds spaced frames as candidate images.
- Each frame has a manifest record marked as user-owned that also identifies its video.

## Acceptance Criteria

- [ ] Frames from a supplied video become candidate images with user-owned manifest records (REQ-8)
- [ ] Each frame's record identifies the video it came from (REQ-8)
- [ ] Kept frames from one video are at least one second apart (REQ-8)

## Edge Cases

- Video file is unreadable → the error names the file; other videos continue (REQ-8)
- Same video is processed twice → no duplicate frames are added (REQ-8)
- Consecutive frames are nearly identical → kept frames are at least one second apart (REQ-8)
- N/A — permission: the user confirms the rights to the videos they supply (REQ-8)

## Notes from implementation

- **Known limitation**: the code asks OpenCV to apply video rotation metadata, but no test covers a clip that carries it, because FFmpeg is not available to create one. Tests cover portrait dimensions only. Check the first phone clip by eye before bulk extraction. /dev, 2026-11-08.
- **Impacts Task 07**: user-owned records carry `video_id`, the grouping key for the same-split rule, and `license: user-owned`, used to count user-video frames.
