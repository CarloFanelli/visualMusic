# Task 02: bell-glow

## Objective

The user sees a glow on the bell, centred on the **sound point**, that grows with volume and shifts colour with **frequency**, and can hide the tracking markers to see the glow alone.

## Context

**Satisfies**: REQ-3, REQ-4, REQ-5, REQ-6, REQ-7

It uses the volume and frequency that the chart task already reads, and the sound point that live tracking already provides.

## Depends on

- Task 01

## Expected Behavior

- A glow is drawn over the image on the sound point and follows it smoothly.
- It grows brighter and larger with volume, and is off below a silence threshold.
- Its colour shifts from warm at 80 Hz to cold at 1600 Hz.
- When the sound point disappears, it fades out within 0.3 seconds.
- A control hides or shows the tracked points and the sound point marker, leaving the glow.

## Acceptance Criteria

- [ ] The glow is centred on the sound point and follows it, mirrored with the camera (REQ-3)
- [ ] A louder sound gives a brighter, larger glow; silence gives none (REQ-4)
- [ ] An 80 Hz tone gives the warm end colour, a 1600 Hz tone the cold end (REQ-5)
- [ ] With the sound point gone, the glow has faded out after 0.3 seconds (REQ-6)
- [ ] The control hides and shows the markers while the glow stays (REQ-7)

## Edge Cases

- Camera image mirrored → the glow sits on the mirrored sound point, like the marker (REQ-3)
- Sound but no sound point → no glow; the chart keeps working (REQ-3)
- Sound point but silence → no glow (REQ-4)
- Volume exactly at the silence threshold → the glow is off (REQ-4)
- Very loud sound, at the recording limit → glow at its maximum, without flickering (REQ-4)
- Frequency below 80 Hz or above 1600 Hz → colour stays at the warm or cold end (REQ-5)
- No frequency recognised but sound present (breath, key noise) → the last colour for up to 0.3 seconds, then neutral white (REQ-5)
- Sound point jumps between the bell centre and the edge midpoint → the glow follows smoothly, without jumping (REQ-6)
- Points hidden, then stop and start again → points are visible again at each new start (REQ-7)
- Microphone refused, or video without sound → no glow; tracking continues (REQ-1, REQ-2)
