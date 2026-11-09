---
feature: live-tracking
version: 1.0
status: approved
completed: true
base: 2f2a1a865696d759276e5c24b528066ca9a12440
---

# Live Tracking

## Overview

A local page shows the saxophone tracked in real time, from a camera or from a recorded video. It draws the points the trained model finds, hides uncertain ones, and highlights the single **sound point** from which later animations will start. It proves the tracking is usable while someone plays. Sound and animations come later.

## Project Context

- Runs on the user's Mac, using the model produced by the existing training.
- The page is reachable only from this computer, like the annotation page.
- Page text is in Italian; code and documents are in English.
- Images and videos never go to GitHub.
- A later feature adds microphone and animations to this same page.
- Without an unseen video, the model's quality in real conditions is still unknown.

## Functional Requirements

### Starting and choosing the source

- REQ-1: One command starts a page reachable only from this computer, where the user chooses a source.
- REQ-2: The user can choose any camera available on this computer as the source.
- REQ-3: The user can choose a video file from this computer as the source.
- REQ-4: A video source plays at normal speed and offers pause and restart.
- REQ-5: A stop control ends tracking, turns the camera off and returns to the source choice.

### What the page shows

- REQ-6: The page shows the source image with each **tracked point** drawn at its matching position.
- REQ-7: A point whose model confidence is below 50% is not drawn.
- REQ-8: The **sound point** is highlighted at the bell centre whenever the bell centre is drawn.
- REQ-9: With the bell centre hidden and both bell edges drawn, the sound point sits midway between the edges.
- REQ-10: In every other case no sound point is shown.
- REQ-11: The page shows "sax non trovato" when no saxophone has been found for more than 0.2 seconds.

### Point movement

- REQ-12: Drawn points tremble less than the model's raw positions when the saxophone stays still.
- REQ-13: A point the model loses stays at its last position for 0.2 seconds, then disappears.

## Data & Dependencies

### Information the feature must retain

Nothing. Images, videos and points exist only while tracking runs.

### External capabilities relied on

- Trained saxophone model: finds the four points, and is the latest one published by training.
- Camera access: needs the user's permission on this computer.

## Non-Functional Requirements

- **Performance** — at least 20 point updates per second on an M1 Pro with a 1080p camera.
- **Performance** — 95% of images have points drawn within 150 ms of being captured.
- **Security** — the page refuses connections from other computers.
- **Security** — no image, video or point is saved or sent outside this computer by this feature.
- **Validation** — a file that cannot be read as video shows an error and returns to the source choice.

## Edge Cases & Error Handling

| Edge Case | Expected Behavior | Relates to |
|-----------|-------------------|------------|
| Trained model missing | The command stops and says to run training first | REQ-1 |
| Model has a different number of points from the saxophone definition | The command stops and explains why | REQ-1 |
| Port already in use | The command stops and says the page may already be open | REQ-1 |
| Page opened in a second tab during tracking | The second tab says tracking is open elsewhere; the first continues | REQ-1 |
| N/A — network: page and program run on the same computer; a stopped program is the row below | — | REQ-1 |
| Program stops while the page is open | The page says the connection was lost and how to restart | REQ-1 |
| No camera found | The camera choice is disabled with an explanation; video remains available | REQ-2 |
| Camera permission refused | The page explains how to grant it; video remains available | REQ-2 |
| Camera in use by another app or disconnected during tracking | Tracking stops with a message and returns to the source choice | REQ-2 |
| Camera image | Shown mirrored, like looking in a mirror, with the points still aligned; a video source is not mirrored | REQ-6 |
| No file chosen | Nothing starts and the source choice stays | REQ-3 |
| Very long or large file | Plays normally, because nothing is kept in memory beyond the current images | REQ-3 |
| File is not a video, or damaged at the start | Error, back to source choice | REQ-3 |
| File damaged partway | Stops at the last good image with a message; restart remains available | REQ-3 |
| Analysis slower than the video | The video keeps normal speed and skips analysing some images | REQ-4 |
| Video ends | The last image stays, with restart available | REQ-4 |
| Pause | Image and points freeze; the 0.2-second timers do not advance | REQ-4 |
| Stop pressed twice, or while still starting | Handled once; the camera ends up off | REQ-5 |
| Tab closed without pressing stop | The program turns the camera off and is ready for a new start | REQ-5 |
| Window resized, or a vertical video | Points stay aligned; the image is never stretched | REQ-6 |
| Two saxophones in the image | Only the one the model is most confident about is tracked | REQ-6 |
| Confidence exactly 50% | The point is drawn | REQ-7 |
| Confidence moving around 50% | The hold in REQ-13 limits flicker | REQ-7 |
| Centre drawn only because it is being held | It still counts as drawn for the sound point | REQ-8 |
| Bell centre lost while both edges are drawn | The sound point moves to the midpoint without vanishing | REQ-9 |
| Only one bell edge, or only the top of the neck | No sound point; the visible points stay drawn | REQ-10 |
| Exactly 0.2 seconds without a saxophone | No message yet: it appears only after 0.2 seconds | REQ-11 |
| Fast real movement | The point follows it; steadying must not visibly trail behind it for over 0.2 seconds | REQ-12 |
| A point reappears after disappearing | It appears at its new position, without sliding from the old one | REQ-13 |

## Out of Scope

- **Microphone and sound** — a following feature, so tracking is judged first.
- **Animations** — they need a proven sound point.
- **Saving a recording with points** — looking at the page is enough to judge the model.
- **Measured accuracy on the test video** — this needs manual marking of its images; judged by eye for now.
- **More than one saxophone** — the project targets one player.
- **Other instruments** — each needs its own points, images and training.
- **New training** — only needed if tracking turns out poor.
