# Task 02: proposal-generation

## Objective

The user can run one command that computes a proposal for every pending image with the latest trained model, and sees how many images got one.

## Context

**Satisfies**: REQ-2

Computing proposals ahead of time keeps the annotation page free of the model and its heavy dependencies. Nothing is shown on the page yet.

## Depends on

- Task 01

## Expected Behavior

- One documented command computes a proposal for each pending image and stores it locally.
- Each proposal holds the four points of the most confident saxophone, all marked visible.
- The command reports how many images got a proposal, how many did not, and how many could not be read.
- Proposals stay out of git, and annotations are never changed.

## Acceptance Criteria

- [ ] Every pending image where the model finds a saxophone gets a stored proposal (REQ-2)
- [ ] An image with several detections gets the points of the most confident one (REQ-2)
- [ ] Annotated and rejected images get no new proposal, and no annotation changes (REQ-2)
- [ ] The command reports counts with, without and unreadable (REQ-2)
- [ ] Stored proposal coordinates always lie inside the image (REQ-2)
- [ ] Proposal files are ignored by git (REQ-2)

## Edge Cases

- No trained model exists → the command stops and names the training command (REQ-2)
- Model finds no saxophone in an image → no proposal is stored and the image counts as without proposal (REQ-2)
- Model finds more than one saxophone → the most confident one is proposed; the user rejects the image if it shows several (REQ-2)
- Image file is missing or unreadable → reported and counted; the other images continue (REQ-2)
- Command runs again after new training or collection → pending images get fresh proposals, a proposal the new model no longer supports is removed, and annotations stay unchanged (REQ-2)
- Command is interrupted → earlier proposals stay usable; running again completes the rest (REQ-2)
- Predicted point falls slightly outside the image → it is placed on the nearest image edge (REQ-3)
- Photo has rotation metadata → points fit the upright image shown on the page (REQ-3)
- Skipped images → the command computes proposals for them too, so they return with their points (REQ-2 · from code)
- Model produces a different number of points than the instrument defines → the command stops, says to train again, and leaves existing proposals untouched (REQ-2 · from code)
