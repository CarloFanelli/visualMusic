---
feature: sound-glow
spec-version: 1.0
status: approved
---

# Architecture Plan: Sound Glow

## Technical Approach

### Overview

Everything happens in the live page's browser code: the Python program is untouched, since sound never reaches it. One audio analysis, fed by the chosen microphone (camera) or by the video element's own audio (video), measures volume and **frequency** about 60 times a second; the chart (task 01) and the glow (task 02) both read that single measurement. No new package: the browser's audio API reads the sound, a small autocorrelation finds the fundamental, and a canvas draws the chart. The page stays one self-contained `index.html`, like the annotation page.

### Shared Concerns

None: each pattern below appears in at most two tasks.

## Per-Task Technical Guidance

### Task 01: sound-chart

**Files to modify:**
- `live_tracking/static/index.html` — microphone list on the source choice; audio start and stop tied to a run; analysis loop; chart canvas inside `#frame`; Italian messages.
- `tests/e2e/test_live_page.py` — a browser with a fake microphone playing a known tone; a video with sound; the edge cases.

**Patterns to reuse:**
- Microphone list: mirror `refreshCameras` (`index.html:120`), filtered on audio inputs.
- Stopping on stop or failure: the per-run resources released in `finish` (`index.html:130`) and the stopped-while-starting check (`index.html:209`).
- Overlay inside the image: position like `#not-found` inside `#frame` (`index.html:38`, `index.html:65`).

**Key decisions:**
- The microphone is requested separately from the camera: a refused microphone must not stop tracking, unlike the camera.
- Volume in decibels below full scale, from -60 to 0, as the horizontal axis; silence threshold at the left end.
- Frequency by autocorrelation over about 2048 samples, accepted only above a clarity threshold, else "not recognised".
- A tone test file for the fake microphone is written by the test with the standard library, so no new dependency.
- `index.html` is 369 lines and grows to about 650: kept as one file, matching the annotation page.

**Watch out for:**
- Browser voice processing (echo cancellation, noise suppression, automatic gain) alters volume and sustained notes — `index.html:204` shows the camera request → microphone request turns all three off; test: tone volume stays constant.
- The video element is `muted` (`index.html:65`): its audio would analyse as silence → unmute for a video, keep muted for the camera; test: a video with sound moves the dot.
- A video element can be connected to the audio API only once → create that connection once per page and reuse it; test: `test_the_same_video_can_be_chosen_again` with sound.
- Tests replacing `getUserMedia` (`test_live_page.py:22`, `:247`) will also catch the microphone request → update them: refused camera only, and count only video streams.
- The audio engine may start suspended when created after awaits → create or resume it in the click handler (`index.html:317`); test: the chart moves on the first start.

---

### Task 02: bell-glow

**Files to modify:**
- `live_tracking/static/index.html` — a glow element in `#frame`, placed on the sound point, sized and coloured from the shared measurement; a "Nascondi punti" control in `#bar`.
- `tests/e2e/test_live_page.py` — glow position, size and colour with tones of known volume and frequency; hidden markers.

**Patterns to reuse:**
- Position and mirroring: `place` (`index.html:103`), as `#sound-point` does in `draw` (`index.html:108`).
- Toggle button in the bar: as `#pause` toggles its label in `togglePause` (`index.html:279`).
- Fake-microphone browser and tone files from task 01.

**Key decisions:**
- The glow is one element with a radial gradient, moved with a short transition, so the jump between bell centre and edge midpoint looks smooth.
- Colour on a hue scale with equal steps per octave, warm at 80 Hz, cold at 1600 Hz; breath or noise holds the last colour 0.3 seconds, then white.
- Opacity fades over 0.3 seconds when the sound point goes; it is driven by the analysis loop, not by frame replies.

**Watch out for:**
- Restarting tracking leaves markers hidden from the previous run → reset the control in `startSource` (`index.html:317`); test: hide, stop, start again, markers visible.
