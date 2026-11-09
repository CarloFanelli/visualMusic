---
feature: live-tracking
spec-version: 1.0
status: approved
---

# Architecture Plan: Live Tracking

## Technical Approach

### Overview

The browser owns the camera and the video: a `<video>` element plays either source, so permissions, playback speed, pause and codecs are the browser's job, and the video file never leaves the page. The page samples the current image at 640 pixels on the long side, posts it as a JPEG to a local Python server, and draws the returned points on an overlay. The server decodes the image, runs the model and returns points; it saves nothing. One request at a time is in flight, so a slow analysis skips images instead of building up delay. No new packages: standard-library server as in `dataset_tools/annotate/server.py`. Checked in installed Chrome: `127.0.0.1` allows camera access and Web Locks, and the user's H.264 `.mov` plays and draws to a canvas.

### Shared Concerns

#### Frame contract

- **Appears in**: Task 02, Task 03, Task 04
- **Reference example**: `live_tracking/server.py` (created in Task 02)
- **Rule**: A session is created when a source starts. Each frame carries the session id and source time in seconds, and gets back positions normalized to the unmirrored image. A session replaced by a newer one gets a conflict, and the page stops.

#### Testing with a scripted model

- **Appears in**: Task 01, Task 02, Task 03, Task 04
- **Reference example**: fake model factory in `tests/test_proposals.py`; Chrome fixture in `tests/e2e/test_annotation_page.py:20`
- **Rule**: Automatic tests use a scripted model, never real weights. Real-model checks are manual.

## Per-Task Technical Guidance

### Task 01: live-page-start

**Files to create:**
- `live_tracking/__init__.py`, `live_tracking/server.py` — command and routes, default port 8766; follow `dataset_tools/annotate/server.py:162-188`.
- `live_tracking/static/index.html` — Italian source choice; reuse the theme tokens of `dataset_tools/annotate/static/index.html:8-18`.
- `dataset_tools/local_server.py` — shared base handler.
- `tests/test_live_server.py`, `tests/e2e/test_live_page.py`.

**Files to modify:**
- `dataset_tools/annotate/server.py` — inherit the send helpers and local-request check instead of duplicating them.
- `dataset_tools/propose.py` — extract the model existence and point-count check as a public function; the live server reuses it.
- `README.md` — document the command.

**Key decisions:**
- A top-level package, because this is not dataset tooling and later features extend it.
- The page polls a small health route, so a stopped program is noticed even with no frames flowing.

**Watch out for:**
- A second program on the same port could go unnoticed, since `HTTPServer.allow_reuse_address` is on — `live_tracking/server.py` → turn the bind error into the requested message; test: start two servers on one port.
- The refactor could weaken the annotation page's protection — `dataset_tools/annotate/server.py:61` → move it unchanged; test: existing forbidden-host tests in `tests/test_annotate_server.py` still pass.

---

### Task 02: camera-tracking

**Files to create:**
- `live_tracking/tracking.py` — pure, no model or network: most confident detection, 50% rule, output points. Mirror `propose.points_of` at `dataset_tools/propose.py:32` for selection and clamping.
- `tests/test_live_tracking.py`.

**Files to modify:**
- `live_tracking/server.py` — session and frame routes; warm the model before serving.
- `live_tracking/static/index.html` — camera list, `<video>`, overlay, stop, messages, Web Locks for the second tab.
- `tests/test_live_server.py`, `tests/e2e/test_live_page.py` — Chrome's fake camera flags, verified working here.

**Key decisions:**
- Web Locks handles the second tab, and releases itself when a tab closes, so no server heartbeats. The session conflict covers a second browser.
- Hidden timing counters on the page let the 20-per-second and 150 ms targets be read during the manual check.

**Watch out for:**
- Edge labels would swap if the mirrored image reached the model — `instruments/saxophone.json` mirror pair → send the unmirrored image, mirror only when drawing; test: asymmetric scripted point lands on the flipped side.
- A late reply could redraw points after stop — `live_tracking/static/index.html` → ignore replies from older sessions; test: stop during a held frame request.
- Oversized frames could exhaust memory, and `MAX_BODY_BYTES` at `dataset_tools/annotate/server.py:18` is too small for images — `live_tracking/server.py` → own 2 MB limit, undecodable images return 400; test: both cases.
- Concurrent frames from two browsers could interleave on one model — `live_tracking/server.py` → one lock around session check and prediction; test: two threads posting.

---

### Task 03: sound-point-steady

**Files to modify:**
- `live_tracking/tracking.py` — per-session state: hold, steadying, sound point, saxophone-found flag; time comes only from the frame's source time.
- `live_tracking/server.py` — one tracker per session; adds sound point and found flag to the reply.
- `live_tracking/static/index.html` — highlighted marker, "sax non trovato".
- `tests/test_live_tracking.py`, `tests/e2e/test_live_page.py`.

**Key decisions:**
- A One Euro filter steadies points: strong when still, weak when moving fast, which fits both requirements with little code.
- All rules live in Python, so timed sequences are tested without a browser.
- A reappearing point resets its filter, so it never slides from the old position.

**Watch out for:**
- Wall-clock time would expire holds during a pause — `live_tracking/tracking.py` → use only the source time from the frame contract; test: a long gap in wall-clock with close source times keeps the point.
- Point names written literally would break if the instrument changes — `instruments/saxophone.json` → stop at start if `bell_centre` or either bell edge is missing; test: instrument without them.

---

### Task 04: video-source

**Files to modify:**
- `live_tracking/static/index.html` — file picker, object URL on the same `<video>`, pause, restart, end and error states; no mirroring. Sample with `requestVideoFrameCallback`.
- `tests/e2e/test_live_page.py` — videos generated with OpenCV.
- `README.md` — how to test on an unseen video, kept out of `data/videos/`.

**Patterns to reuse:**
- Frame contract (see Shared Concerns); camera loop from Task 02.

**Key decisions:**
- Restart creates a new session, because source time jumps backward and old holds must not carry over.
- Nothing changes on the server: the browser handles the file.

**Watch out for:**
- Fixtures encoded as `mp4v` fail in Chrome with error 4, verified here — `tests/e2e/test_live_page.py` → generate `avc1` or `VP80`; test: fixture plays before assertions.
- Replaced videos could stay in memory — `live_tracking/static/index.html` → revoke the object URL on stop and on a new choice; test: not observable automatically, checked in review.
- A failure partway must not look like a bad file — `live_tracking/static/index.html` → check whether data already loaded before choosing the message; test: truncated file.
