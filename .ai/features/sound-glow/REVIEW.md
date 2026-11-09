---
feature: sound-glow
status: APPROVED
reviewed: 2026-11-09
head: 866f1865ca352ef489cdcd3277177ea9cc004338
---

# Review — sound-glow

**Scope**: 2 files (re-verification — delta since review head `b4e1e821`; 1 workflow artifact under `.ai/` excluded)
**Findings**: 0 must-fix · 0 should-fix · 0 nit

## Findings

### F-1 · nit · bug · glow spills outside the image   [ADDRESSED]
**File**: `live_tracking/static/index.html:38`
**Issue**: `#frame` does not clip its content, so a glow up to 45% of the image wide, centred on a sound point near the image edge, spreads over the page background beside the image, visibly in dark mode.
**Change**: Add `overflow: hidden` to `#frame`, so the glow stays over the image.
**Why**: REQ-3 draws the glow over the image.

### F-2 · should-fix · bug · brightness lags behind the note attack   [ADDRESSED]
**File**: `live_tracking/static/index.html:44`, `live_tracking/static/index.html:275`
**Issue**: The 300 ms opacity transition applies to every brightness change, and the analysis loop sets a new opacity each frame, so a note starting from silence reaches only about a third of its brightness after 100 ms.
**Change**: Keep the 300 ms opacity transition only for fading out when the sound point is gone or the sound stops (the `else` branch of `shine`), and set the brightness without transition while sound drives it.
**Why**: The spec requires the glow to react within 100 ms of a change in the sound; REQ-6 asks for the 0.3-second fade only when the sound point disappears.

### F-3 · nit · dup · refused-microphone script written twice   [ADDRESSED]
**File**: `tests/e2e/test_live_page.py:258-262`, `tests/e2e/test_live_page.py:950-954`
**Issue**: The same five-line script that refuses the microphone is repeated in two tests.
**Change**: Move it to one module constant beside `REFUSED` (`tests/e2e/test_live_page.py:26`) and use it in both tests.

### F-4 · nit · simplify · tone file packed one sample at a time   [ADDRESSED]
**File**: `tests/e2e/test_live_page.py:68`
**Issue**: `write_tone` packs 96,000 samples one by one with `struct`, while the sound is already a numpy array.
**Change**: Write `(amplitude * 32767 * sound).round().astype("<i2").tobytes()` and drop the `struct` import, as `write_video` builds its frames with numpy (`tests/e2e/test_live_page.py:548`).
