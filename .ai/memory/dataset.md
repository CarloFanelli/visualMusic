# Dataset

Collecting licensed images, marking points on them and exporting them for training.

## Terms

### Proposal
The points a trained model suggests for one pending image. It becomes an **annotation** only when the user confirms it, so export and training never read it.
_Avoid_: prediction, for points shown on the page; annotation, which is reserved for points the user confirmed.

## Decisions

- **Point names and labels are separate**: each point has a stable English `name`, stored in annotations, and a `label`, shown to the user. Why: changing a label must not send annotated images back to pending.
- **A reopened image is corrected, not marked again**: it shows its saved points, which move as on a **proposal**, and nothing changes until the user confirms. Why: a small fix should not cost four clicks, and a stray click must not overwrite saved work.
- **Skipped images wait for a button**: when pending images run out, the page shows the skipped count and a button to resume them. Why: it keeps both the return of skipped images and the completion message.

## Gotchas

- **Manifest paths are untrusted**: the manifest can be edited by hand or come from someone else, so a `file` value like `../x.jpg` can delete or overwrite files outside the data folders. Code that writes or deletes through this field must first require a plain file name.
- **License names need exact matching**: `CC BY SA 4.0` and `CC BY 4.0 NC` once passed as plain CC BY, one because only the second word was read and one because `NC` looked like a country code. Add any new license form to the rejection tests too.
- **The browser keeps the old image while the next one loads**: a click in that moment lands on the wrong image without any error. Check that the image has finished loading before accepting a point.
- **Wikimedia limits file downloads hard**: `upload.wikimedia.org` imposed a 600-second wait when asked for one file per second, so that host needs a longer interval than the others.
- **Delaying a page load in Playwright tests**: a sleep inside a route handler blocks Playwright itself, so the image finishes loading before the next click and the test proves nothing. Hold the route and release it after the click.
- **Ultralytics sends usage events during training**: its `sync` setting is on by default, though no images are sent. It can be turned off with `.venv/bin/yolo settings sync=False`.
- **The 10-epoch trial says nothing about point quality**: on the same 225 images, the neck's median error was 16% of the image after 10 epochs and 1.5% after 100. Use the trial to prove the pipeline works, and judge a model only after a full training.
- **Keep the project out of iCloud**: inside the synced Desktop it collected 272 numbered copies in the export and 1216 in `data/annotations/`, and online-only files blocked any program reading them. A copied image without its label trains as an image with no saxophone, so the project must stay in a folder that is not synced.
- **Corrected annotations are not an independent test**: 69% of visible points on reviewed images were kept exactly where the **proposal** placed them, so the model's error against them looks better than it is. Judge point positions on images marked without a proposal, or on an unseen video.
