# Task 04: correct-points

## Objective

The user can fix a proposal by moving, hiding or restoring single points, and can correct an annotated image the same way instead of marking it again from scratch.

## Context

**Satisfies**: REQ-4, REQ-5, REQ-6, REQ-7, REQ-13

This completes the correction flow. Reopening an annotated image changes: today a click starts the four points again, while now the saved points are moved.

## Depends on

- Task 03

## Expected Behavior

- Dragging a point moves it, and the other points stay where they are.
- A list shows the four points; selecting one and clicking the image moves it there.
- The selected point can be marked not visible, and placing it again brings it back.
- Annulla reverts the last move or hide.
- Reopening an annotated image shows its saved points, editable the same way, saved with Enter or Conferma.

## Acceptance Criteria

- [ ] Dragging a point changes only that point, and its new position is saved on confirm (REQ-4)
- [ ] Selecting a point in the list and clicking the image moves that point (REQ-5)
- [ ] The selected point can be marked not visible and is saved without a position (REQ-6)
- [ ] Clicking the image with a hidden point selected makes it visible there (REQ-6)
- [ ] Annulla reverts one move or hide at a time (REQ-7)
- [ ] A reopened annotated image shows editable saved points and saves them on confirm (REQ-13)

## Edge Cases

- Point is dragged beyond the image → it stops at the image edge (REQ-4)
- Several points overlap → dragging moves the top one; the list reaches the others (REQ-4, REQ-5)
- No point is selected and the image is clicked → nothing changes, so a stray click never moves a point (REQ-5)
- Selected point is hidden and the image is clicked → the point becomes visible at that position (REQ-6)
- Every point is marked not visible → cannot be confirmed; the user is asked to reject the image or undo (REQ-6, REQ-8)
- Annulla with no change made → nothing changes (REQ-7)
- Saving fails after moves → stays on the image, keeps the moved points, shows an error and retry (REQ-8)
- Page is reloaded before confirming → moves are discarded; the image shows its proposal again (REQ-9)
- Reopened image is left without confirming → its saved points stay unchanged (REQ-13)
