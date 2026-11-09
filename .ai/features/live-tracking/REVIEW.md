---
feature: live-tracking
status: APPROVED
reviewed: 2026-11-09
head: 2e727bc08e1da5d4ca9cdbd734077639c5485a6a
---

# Review — live-tracking

**Scope**: 9 files (re-verification — delta since review head `2e727bc0`; 2 workflow artifacts under `.ai/` excluded)
**Findings**: 0 must-fix · 0 should-fix · 0 nit

## Findings

### F-1 · should-fix · security · invalid frame length is not refused   [ADDRESSED]
**File**: `live_tracking/server.py:86-90`
**Issue**: A negative `Content-Length` passes the size limit and `rfile.read(-1)` waits until the client closes, bypassing the 2 MB limit; a non-numeric one raises an uncaught `ValueError` and closes the connection with no reply.
**Change**: Answer 400 when the length is not a number or is negative, handling `ValueError` as in `dataset_tools/annotate/server.py:121-129`.

### F-2 · should-fix · bug · frame with no session crashes before any session   [ADDRESSED]
**File**: `live_tracking/server.py:99-105`
**Issue**: A frame with no `session` before any session exists passes the check because `None` equals `None`, then `self.tracker.update` fails on the missing tracker and the connection drops.
**Change**: Treat a missing session parameter as a conflict and answer 409 before reaching the model.

### F-3 · should-fix · bug · model failure looks like a lost connection   [ADDRESSED]
**File**: `live_tracking/server.py:104-105`
**Issue**: An exception from the model drops the connection, so the page ends tracking with "connection lost, restart the program" although the program is running, and the next health check then erases that message, leaving no explanation.
**Change**: Catch `RuntimeError` from the prediction and answer 500, so the page reaches its existing "could not analyse an image" message.

### F-4 · should-fix · bug · closing the tab prints a crash in the terminal   [ADDRESSED]
**File**: `live_tracking/server.py:106`
**Issue**: A tab closed while a frame is being analysed makes the reply raise `BrokenPipeError`, and the terminal shows a full traceback for a normal action, which is likely since a frame is nearly always in flight.
**Change**: Ignore `BrokenPipeError` and `ConnectionResetError` when sending the frame reply.

### F-5 · should-fix · bug · double click shows a false "open elsewhere" message   [ADDRESSED]
**File**: `live_tracking/static/index.html:310-320`
**Issue**: `current` is set only inside the asynchronous lock callback, so a double click on the camera button requests the lock twice, and the second request shows "already open in another tab" for the whole run while this same tab tracks normally.
**Change**: Mark the start as in progress before requesting the lock, and clear that mark when the lock callback has run, so a second click is ignored.

### F-6 · should-fix · convention · no test proves pause keeps the timers still   [ADDRESSED]
**File**: `tests/e2e/test_live_page.py:423`
**Issue**: The page could send wall-clock time for a video and every test would still pass, because no test checks the time sent after a pause, so the criterion about the 0.2-second timers during pause is unproven.
**Change**: In the style of `test_pause_freezes_image_and_points`, pause for over 0.5 seconds, resume, and assert the `time` of the next frame request is within 0.3 seconds of the time at which the video froze.

### F-7 · should-fix · convention · the successful start of the command is untested   [ADDRESSED]
**File**: `tests/test_live_server.py:53`
**Issue**: The tests run `main` only on its failure paths, so nothing proves that the command prints the address, warms the model up once and exits cleanly on Ctrl+C.
**Change**: Add a test using the `start` fixture with `serve_forever` patched to raise `KeyboardInterrupt`, asserting exit code 0, the printed address and one prediction on the model.

### F-8 · nit · bug · point lost in a gap between images is not reset   [ADDRESSED]
**File**: `live_tracking/tracking.py:81-85`
**Issue**: Expired points are removed after the update, so a point seen again after more than 0.2 seconds with no image in between goes through the filter from its old position, ending about 1% of the image short of the new one on the first image.
**Change**: Remove expired points before applying the new detections, keeping the removal after them too for points not seen in this image.

### F-9 · nit · bug · the exact 0.2-second boundary depends on rounding   [ADDRESSED]
**File**: `live_tracking/tracking.py:85`, `live_tracking/tracking.py:94`
**Issue**: `5.3 - 5.1` gives `0.20000000000000018`, so at exactly 0.2 seconds a point can vanish and "sax non trovato" can appear one image early.
**Change**: Add a small tolerance such as one microsecond to both comparisons, using one shared constant.

### F-10 · nit · bug · image is cropped while a message is showing   [ADDRESSED]
**File**: `live_tracking/static/index.html:38`
**Issue**: The image height calculation ignores the message bar, so when a message shows during tracking, such as a damaged video, the image overflows its area and loses about 10 pixels at top and bottom.
**Change**: Size the image from the space actually available in the stage rather than from the window height.

### F-11 · nit · bug · a camera that fails to play reports a lost connection   [ADDRESSED]
**File**: `live_tracking/static/index.html:215-221`
**Issue**: A failure of `view.play()` for the camera shares the catch of the session request, so a camera problem tells the user to restart the program.
**Change**: Handle `view.play()` separately with the existing camera message, leaving the lost-connection message to the session request.

### F-12 · nit · bug · a stopped restart can touch the next source   [ADDRESSED]
**File**: `live_tracking/static/index.html:297-299`
**Issue**: If stop is pressed during the restart's session request and another source starts at once, the old restart then seeks and plays the shared video element.
**Change**: Return right after the session request when `run.finished` is true.

### F-13 · nit · dup · serving loop repeated in both local pages   [ADDRESSED]
**File**: `live_tracking/server.py:138-145`, `dataset_tools/annotate/server.py:153-160`
**Issue**: Eight identical lines print the address and run the server until Ctrl+C.
**Change**: Move them into one function in `dataset_tools/local_server.py` and call it from both commands.

### F-14 · nit · convention · test name says two threads but uses six   [ADDRESSED]
**File**: `tests/test_live_server.py:201`
**Issue**: `test_frames_from_two_threads_never_run_on_the_model_at_once` starts six threads.
**Change**: Rename it `test_frames_from_many_threads_never_run_on_the_model_at_once`.

### F-15 · nit · dead · fixture sets a value that is already set   [ADDRESSED]
**File**: `tests/test_live_server.py:59`
**Issue**: The `start` fixture sets `FakeModel.points` to the value it already has, and the test that changes it is restored by `monkeypatch`.
**Change**: Delete the line.

### F-16 · nit · dup · two builders for the same model result   [ADDRESSED]
**File**: `tests/test_live_tracking.py:14-23`, `tests/test_live_tracking.py:30`, `tests/test_live_tracking.py:57-64`
**Issue**: `result` and `detection` build the same shape, and one test rebuilds the empty result that `NOTHING` already holds.
**Change**: Keep `result`, express `detection` through it, and use `NOTHING` in `test_no_saxophone_gives_no_points`.

### F-17 · nit · bug · test leaves the request socket open   [ADDRESSED]
**File**: `tests/test_live_server.py:253`
**Issue**: Replacing `shutdown_request` with a lambda that only sets an event stops the server from closing that connection, so the socket stays open until garbage collection.
**Change**: Keep the original method and call it before setting the event, as `predict` is kept and called in the same test.
