# Dataset

Collecting licensed images, marking points on them and exporting them for training.

## Decisions

- **Point names and labels are separate**: each point has a stable English `name`, stored in annotations, and a `label`, shown to the user. Why: changing a label must not send annotated images back to pending.
- **A reopened image is marked again in full**: the first click starts a new set of points that replaces the saved one on save, and single points cannot be moved. Why: it keeps one simple click flow for new and reopened images.
- **Skipped images wait for a button**: when pending images run out, the page shows the skipped count and a button to resume them. Why: it keeps both the return of skipped images and the completion message.

## Gotchas

- **Manifest paths are untrusted**: the manifest is versioned and can come from a contributor, so a `file` value like `../x.jpg` can delete or overwrite files outside the data folders. Code that writes or deletes through this field must first require a plain file name.
- **License names need exact matching**: `CC BY SA 4.0` and `CC BY 4.0 NC` once passed as plain CC BY, one because only the second word was read and one because `NC` looked like a country code. Add any new license form to the rejection tests too.
- **The browser keeps the old image while the next one loads**: a click in that moment lands on the wrong image without any error. Check that the image has finished loading before accepting a point.
- **Wikimedia limits file downloads hard**: `upload.wikimedia.org` imposed a 600-second wait when asked for one file per second, so that host needs a longer interval than the others.
- **Delaying a page load in Playwright tests**: a sleep inside a route handler blocks Playwright itself, so the image finishes loading before the next click and the test proves nothing. Hold the route and release it after the click.
- **Ultralytics sends usage events during training**: its `sync` setting is on by default, though no images are sent. It can be turned off with `.venv/bin/yolo settings sync=False`.
