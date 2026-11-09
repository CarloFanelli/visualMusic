# Task 01: live-page-start

## Objective

The user runs one command and opens a local page offering the choice of source, or gets a clear reason why it cannot start.

## Context

**Satisfies**: REQ-1

Everything else needs a running page and a usable model, so this comes first. Later tasks add behavior to the sources shown here.

## Depends on

None

## Expected Behavior

- One command loads the latest trained model and prints the address of the page.
- The page, in Italian, offers a camera and a video file as sources; they become usable in Tasks 02 and 04.
- Requests from other computers, and from other websites open in the browser, are refused.
- If the program stops while the page is open, the page says so and how to restart it.

## Acceptance Criteria

- [ ] The command starts a page that shows the source choice (REQ-1)
- [ ] The page is unreachable from other computers and refuses requests from other websites (REQ-1)
- [ ] Without a trained model, the command stops and says to run training (REQ-1)
- [ ] A model with the wrong number of points stops the command with an explanation (REQ-1)
- [ ] With the port in use, the command stops and says the page may already be open (REQ-1)
- [ ] Stopping the program makes the open page show how to restart it (REQ-1)

## Edge Cases

- Trained model missing → the command stops and says to run training first (REQ-1)
- Model has a different number of points from the saxophone definition → the command stops and explains why (REQ-1)
- Port already in use → the command stops and says the page may already be open (REQ-1)
- Program stops while the page is open → the page says the connection was lost and how to restart (REQ-1)
