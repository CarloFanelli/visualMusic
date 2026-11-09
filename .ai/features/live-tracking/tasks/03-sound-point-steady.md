# Task 03: sound-point-steady

## Objective

The user sees one highlighted **sound point** on the bell, and tracked points that move steadily instead of trembling or flickering.

## Context

**Satisfies**: REQ-8, REQ-9, REQ-10, REQ-11, REQ-12, REQ-13

The camera loop must exist first, so these rules can be judged on a real moving image. They come before video so both sources share them.

## Depends on

- Task 02

## Expected Behavior

- The sound point is highlighted at the bell centre when it is drawn, otherwise midway between two drawn bell edges, otherwise absent.
- Points tremble less while the saxophone stays still, and still follow fast movement.
- A lost point stays at its last position for 0.2 seconds, then disappears.
- After more than 0.2 seconds with no saxophone, the page shows "sax non trovato".

## Acceptance Criteria

- [ ] The sound point follows the bell centre whenever the centre is drawn (REQ-8)
- [ ] With the centre hidden and both edges drawn, the sound point sits at their midpoint (REQ-9)
- [ ] With neither condition met, no sound point is shown (REQ-10)
- [ ] "sax non trovato" appears only after more than 0.2 seconds without a saxophone (REQ-11)
- [ ] On a still saxophone, drawn positions vary less than the model's raw positions (REQ-12)
- [ ] A lost point holds for 0.2 seconds, then disappears (REQ-13)

## Edge Cases

- Confidence moving around 50% → the 0.2-second hold limits flicker (REQ-7)
- Centre drawn only because it is being held → it still counts as drawn for the sound point (REQ-8)
- Bell centre lost while both edges are drawn → the sound point moves to the midpoint without vanishing (REQ-9)
- Only one bell edge, or only the top of the neck → no sound point; the visible points stay drawn (REQ-10)
- Exactly 0.2 seconds without a saxophone → no message yet: it appears only after 0.2 seconds (REQ-11)
- Fast real movement → the point follows it; steadying must not visibly trail behind it for over 0.2 seconds (REQ-12)
- A point reappears after disappearing → it appears at its new position, without sliding from the old one (REQ-13)
