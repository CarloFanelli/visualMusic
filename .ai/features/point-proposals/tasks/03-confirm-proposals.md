# Task 03: confirm-proposals

## Objective

The user sees pending images with their four points already placed and saves a correct one with Enter or Conferma; images without a proposal arrive afterwards and are clicked by hand.

## Context

**Satisfies**: REQ-3, REQ-8, REQ-9, REQ-10, REQ-11, REQ-12

This delivers the main time saving. Moving points arrives in the next task; until then a wrong proposal can be skipped or rejected.

## Depends on

- Task 02

## Expected Behavior

- A pending image with a proposal opens with its four points shown, with no click needed.
- Clicking the image does not change a proposal.
- Enter or Conferma saves the shown points as an annotation and opens the next image.
- Images with a proposal open first; images without one open afterwards and work as today.
- Progress shows how many pending images have a proposal and how many do not.
- Salta, Non adatta and Ripristina work as on any other image.

## Acceptance Criteria

- [ ] A pending image with a proposal shows four points with no click (REQ-3)
- [ ] Enter and Conferma each save the points and open the next image (REQ-8)
- [ ] A saved confirmation has the same format as a hand-made annotation (REQ-8)
- [ ] An unconfirmed proposal creates no annotation and is left out of export (REQ-9)
- [ ] Salta and Non adatta store their usual status on an image with a proposal (REQ-10)
- [ ] All images with a proposal open before any without one (REQ-11)
- [ ] Progress shows the counts of pending images with and without a proposal (REQ-12)

## Edge Cases

- Proposal file is unreadable or uses other point names → treated as no proposal; the image is marked by hand (REQ-3)
- Proposal cannot be fetched from the page → the image opens for clicking by hand, with a message (REQ-3)
- Enter is held down → only one image is confirmed (REQ-8)
- Enter is pressed again as the next image appears → ignored for the first 300 ms, so no image is confirmed unseen (REQ-8)
- Enter or Conferma before the image has loaded → ignored (REQ-8)
- Focus is on another button when Enter is pressed → Enter confirms and that button does not fire (REQ-8)
- Saving fails → stays on the image, shows an error and retry (REQ-8)
- Last image is confirmed → shows completion and the remaining skipped count (REQ-8)
- Same image is open in two tabs → the last save wins (REQ-8)
- Page is reloaded before confirming → the image shows its proposal again (REQ-9)
- Proposal exists but the image has never been confirmed → the image stays pending and is left out of export (REQ-9)
- Skipped image returns later → it opens with its proposal (REQ-10)
- Rejected image is restored → it becomes pending and opens with its proposal, if any (REQ-10)
- No proposals exist at all → every image is marked by hand, as today (REQ-11)
- Only images without a proposal remain → they open one by one for clicking (REQ-11)
- Proposals are recomputed while the page is open → counts update on reload; the next image uses the newest proposal (REQ-12)
- Enter on an image without a proposal → ignored, and no focused button fires (REQ-8 · from code)
