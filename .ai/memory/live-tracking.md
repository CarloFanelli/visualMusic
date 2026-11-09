# Live Tracking

Following the saxophone in real time from a camera or a recorded video.

## Terms

### Tracked point
A point the trained model finds while tracking runs, on a live or recorded image. It exists only during tracking and is never saved.
_Avoid_: proposal, which is reserved for suggestions on an image to annotate; annotation, which the user confirmed.

### Sound point
The single position treated as where sound leaves the instrument. It is the bell centre, or the midpoint of the two bell edges when the centre is hidden and both edges are drawn.
_Avoid_: bell centre, which is only one of its two possible sources.

## Gotchas

- **Source time rounding**: subtracting decimal source times gives values like 0.20000000000000018, so a strict comparison with the 0.2-second hold drops points one image early. Compare with a small tolerance.
- **Camera button starts disabled**: the page enables the camera button only after listing the cameras, so a browser test that clicks it at once does nothing. Wait for it to be enabled first.
- **Tab closed during analysis**: the reply to a frame then fails with a broken or reset connection. That is a normal way to stop, so the server ignores it instead of printing a traceback.
