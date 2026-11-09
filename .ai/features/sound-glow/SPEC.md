---
feature: sound-glow
version: 1.0
status: approved
completed: true
base: 6a7311ee288a669f61664fd8337ad38885c44224
---

# Sound Glow

## Overview

While tracking runs, a glow lights up around the **sound point**, driven by the sound of the instrument: brighter and larger when louder, warm in low frequencies and cold in high ones. A small chart in the corner shows the current volume horizontally and **frequency** vertically, with a fading trail. Sound comes from a chosen microphone with the camera, or from the video's own audio with a recorded video. It is the first, basic visual effect; richer effects come later.

## Project Context

- Extends the existing live tracking page; tracking behaviour stays as it is.
- The page is reachable only from this computer; page text is in Italian.
- Sound is analysed in the browser; the Python program is not involved in sound.
- Frequency means the fundamental frequency in hertz, never a note name.
- The tenor saxophone's fundamentals fall roughly between 100 and 1200 Hz.

## Functional Requirements

### Sound source

- REQ-1: With the camera source, the user can choose any microphone available on this computer.
- REQ-2: With a video source, sound comes from the video's own audio, which is also heard.

### Glow

- REQ-3: A glow is drawn over the image, centred on the sound point, following it as it moves.
- REQ-4: The glow grows brighter and larger with volume, and is off below a silence threshold.
- REQ-5: The glow's colour shifts from warm at 80 Hz to cold at 1600 Hz.
- REQ-6: When the sound point disappears, the glow fades out within 0.3 seconds.
- REQ-7: A control hides or shows the tracked points and the sound point marker; the glow stays.

### Chart

- REQ-8: A small chart in the bottom-right corner of the image shows a dot at the current volume and frequency.
- REQ-9: Its horizontal axis goes from silence to the loudest sound the source can record.
- REQ-10: Its vertical axis covers 80 to 1600 Hz, with equal space per octave, labelled in hertz.
- REQ-11: The dot leaves a trail that fades within 2 seconds.
- REQ-12: When no frequency can be recognised, the dot is not shown.

## Data & Dependencies

### Information the feature must retain

Nothing. Sound is analysed as it arrives and never recorded.

### External capabilities relied on

- Microphone access: needs the user's permission on this computer.

## Non-Functional Requirements

- **Performance** — glow and dot react within 100 ms of a change in the sound.
- **Performance** — tracking keeps at least 20 point updates per second with the glow and chart on.
- **Validation** — a steady note's frequency is shown within 3% of its true value (about half a semitone).
- **Security** — the microphone is on only while camera tracking runs, and is turned off by stop.
- **Security** — no sound is saved or sent anywhere.

## Edge Cases & Error Handling

| Edge Case | Expected Behavior | Relates to |
|-----------|-------------------|------------|
| Microphone permission refused | Tracking continues without glow and chart; a message explains how to grant it | REQ-1 |
| No microphone found | The microphone choice is disabled with an explanation; tracking works without effects | REQ-1 |
| Microphone in use or unplugged during tracking | Tracking continues, glow and chart stop, a message says so | REQ-1 |
| Stop pressed, or tab closed | The microphone is turned off | REQ-1 |
| Second tab | Already blocked by tracking; it never opens the microphone | REQ-1 |
| N/A — network: sound never leaves the browser | — | REQ-1 |
| Video without an audio track | Glow and chart stay off; a message says the video has no sound | REQ-2 |
| Video paused, ended or restarted | Sound stops, so the glow goes off and the trail fades; restart resumes both | REQ-2 |
| Camera image mirrored | The glow sits on the mirrored sound point, like the marker | REQ-3 |
| Sound but no sound point | No glow; the chart keeps working | REQ-3 |
| Sound point but silence | No glow | REQ-4 |
| Volume exactly at the silence threshold | The glow is off | REQ-4 |
| Very loud sound, at the recording limit | Glow at its maximum, without flickering | REQ-4 |
| Frequency below 80 Hz or above 1600 Hz | Colour stays at the warm or cold end | REQ-5 |
| No frequency recognised but sound present (breath, key noise) | The glow keeps the last colour for up to 0.3 seconds, then turns neutral white | REQ-5 |
| Sound point jumps between the bell centre and the edge midpoint | The glow follows smoothly, without jumping | REQ-6 |
| Points hidden, then stop and start again | Points are visible again at each new start | REQ-7 |
| Window resized or vertical video | Chart stays in the corner, the same size, inside the image | REQ-8 |
| Frequency outside 80–1600 Hz | The dot sits on the top or bottom edge of the chart | REQ-10 |
| Two sounds at once (multiphonics, background music) | The chart shows the strongest frequency, or no dot if none prevails | REQ-12 |
| Silence | No dot; the trail fades | REQ-12 |

## Out of Scope

- **Rings, particles, trail, spectrum, ripple** — further effects, once the glow is proven.
- **Black background without the image** — chosen to see the glow on the image first.
- **Note names** — the user wants frequency ranges, not notes.
- **Recording the result** — looking at the page is enough for now.
- **Live microphone over a recorded video** — the video's own audio was preferred.
