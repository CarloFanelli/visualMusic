# Task 01: sound-chart

## Objective

While tracking runs, the user sees a small chart in the corner of the image showing the current volume and **frequency** of the sound, from a chosen microphone or from the video's own audio.

## Context

**Satisfies**: REQ-1, REQ-2, REQ-8, REQ-9, REQ-10, REQ-11, REQ-12

Sound input and its analysis come first: the chart makes them visible and checkable on their own, before any effect depends on them.

## Depends on

None

## Expected Behavior

- On the source choice, the user picks a microphone from a list, like the camera.
- With the camera, sound comes from that microphone; with a video, from the video's audio, which is heard.
- A small chart in the bottom-right corner of the image shows a dot: volume horizontally, frequency vertically.
- The vertical axis covers 80 to 1600 Hz with equal space per octave, labelled in hertz.
- The dot leaves a trail that fades within 2 seconds, and is not shown when no frequency is recognised.

## Acceptance Criteria

- [ ] Every microphone on this computer can be chosen, and camera tracking uses the chosen one (REQ-1)
- [ ] With a video, its audio is heard and drives the chart (REQ-2)
- [ ] The chart sits in the bottom-right corner of the image during tracking (REQ-8)
- [ ] Louder sound moves the dot right; silence puts it at the left end (REQ-9)
- [ ] A steady 220 Hz tone puts the dot at the 220 Hz height, within 3% (REQ-10)
- [ ] Earlier positions remain as a trail that is gone after 2 seconds (REQ-11)
- [ ] With silence or no recognisable frequency, no dot is shown (REQ-12)

## Edge Cases

- Microphone permission refused → tracking continues without the chart; a message explains how to grant it (REQ-1)
- No microphone found → the microphone choice is disabled with an explanation; tracking works without effects (REQ-1)
- Microphone in use or unplugged during tracking → tracking continues, the chart stops, a message says so (REQ-1)
- Stop pressed, or tab closed → the microphone is turned off (REQ-1)
- Second tab → already blocked by tracking; it never opens the microphone (REQ-1)
- Video without an audio track → the chart stays off; a message says the video has no sound (REQ-2)
- Video paused, ended or restarted → sound stops, so the trail fades; restart resumes it (REQ-2)
- Window resized or vertical video → the chart stays in the corner, the same size, inside the image (REQ-8)
- Frequency outside 80–1600 Hz → the dot sits on the top or bottom edge of the chart (REQ-10)
- Two sounds at once (multiphonics, background music) → the strongest frequency, or no dot if none prevails (REQ-12)
- Silence → no dot; the trail fades (REQ-12)
