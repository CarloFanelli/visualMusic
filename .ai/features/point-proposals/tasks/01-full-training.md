# Task 01: full-training

## Objective

The user can train the model fully with one command, and a successful result becomes the model used for proposals.

## Context

**Satisfies**: REQ-1

Until now the full training was an ad-hoc run and only the 10-pass trial was a command. Proposals need a known model to read, so this comes first.

## Depends on

None

## Expected Behavior

- One documented command trains for 100 passes on the exported dataset, starting from the base model.
- When training ends successfully, its best result becomes the latest trained model.
- The command states where the model was saved.
- The existing trial command keeps working as before.

## Acceptance Criteria

- [ ] The command trains for exactly 100 passes on the exported dataset (REQ-1)
- [ ] After success, the latest trained model is the best result of that training (REQ-1)
- [ ] After a failed training, the previous latest model is unchanged (REQ-1)
- [ ] The trial command still trains for 10 passes and draws its validation images (REQ-1)

## Edge Cases

- Exported dataset is missing → training stops and names the export command (REQ-1)
- Training fails or is interrupted → the previous model stays in use and the error is shown (REQ-1)
- Apple GPU fails during training → falls back to CPU with a visible notice (REQ-1)
