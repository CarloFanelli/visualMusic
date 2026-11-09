# Sound Effects

Visual effects on the live tracking page, driven by the instrument's sound.

## Terms

### Frequency
The fundamental frequency of the sound, in hertz, as shown on the chart and used for the glow colour. It is never turned into a note name.
_Avoid_: note or pitch name, because the user wants frequency ranges, not notes.

## Gotchas

- **CSS transitions on values set every frame**: a property updated on every animation frame with a CSS transition restarts the transition each frame, so it lags far behind the sound (a 300 ms opacity transition left a note's glow at a third of its brightness after 100 ms). Apply the transition only for the fade-out, and set sound-driven values without one.
- **Chrome's fake microphone is not silent**: the default fake microphone in tests beeps loudly from time to time. Tests that need silence, or a known tone, feed it a WAV file with `--use-file-for-fake-audio-capture`.
- **A video element connects to the audio graph only once**: `createMediaElementSource` fails the second time for the same element, so the connection is made once per page and reused for every video.
