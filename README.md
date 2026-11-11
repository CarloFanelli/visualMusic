# visualMusic

Tracks the point where sound leaves a musical instrument, starting with the tenor saxophone, and draws visual effects there from the sound being played.

The project has two parts:

- **Dataset tools** collect openly licensed saxophone images, let you mark four points on each one in a local page, and train an Ultralytics YOLO pose model on them.
- **Live tracking** follows the saxophone from a camera or a video in the browser, and lights a glow on the bell driven by the volume and frequency of the sound.

Everything runs on your own computer: no image, video or sound is sent anywhere.

## Setup

Requires Python 3.11 or newer on Apple Silicon. This command creates an isolated environment in `.venv` and is safe to run again:

```shell
scripts/setup.sh
```

Check the environment:

```shell
.venv/bin/python -m dataset_tools.check_env
```

Run the tests:

```shell
.venv/bin/python -m pytest
```

The tests of the annotation page drive the Chrome installed on this computer, and are skipped unless the development tools are installed:

```shell
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Collect images

Gathers candidate saxophone images from Wikimedia Commons, Open Images and Openverse, keeping only CC0, public domain and CC BY images. The first run takes several minutes before the first Open Images download, because it scans very large metadata files. Run it again at any time: it adds only new images.

```shell
.venv/bin/python -m dataset_tools.collect
```

Use `--limit N` to stop after N new images per source. Licenses are those declared by each source: this reduces legal risk but gives no absolute guarantee.

## Add frames from your videos

Put your own videos in `data/videos/`, then run this command. It keeps one frame per second and is safe to run again. Use only videos you have the rights to.

```shell
.venv/bin/python -m dataset_tools.frames
```

## Restore images on a fresh clone

Downloads missing online-sourced images listed in the manifest. A file is kept only if it matches its recorded fingerprint.

```shell
.venv/bin/python -m dataset_tools.restore
```

## Mark the points

Starts a page reachable only from this computer. Images with a proposal come first: check the points already placed and press **Invio** or **Conferma** to save and open the next one. Nothing is saved until you confirm. Images without a proposal come afterwards: click the requested points in order, and each image saves automatically. Stop with Ctrl+C at any time and start again later to resume.

```shell
.venv/bin/python -m dataset_tools.annotate.server
```

To correct a point, drag it, or select it in the list on the left and click where it belongs: the list also reaches points that overlap. Select a point and use **Punto non visibile** to hide it, and place it again to bring it back. **Annulla** reverts the last change. From the keyboard, keys 1 to 4 select a point, the arrows move it by one screen pixel, and Backspace hides it. **S** hides or shows all the points on screen, to see the photo underneath, without changing them. An annotated image reopened from the list works the same way, and stays unchanged until you confirm.

While clicking by hand, **Annulla** removes the last point and **Punto non visibile** marks a hidden point. On any image, **Salta** postpones it and **Non adatta** discards it, for example a soprano, several saxophones or no saxophone. A discarded image can be restored by opening it from the list.

Point names and their order are in `instruments/saxophone.json`. If you change them, images already annotated return to pending, and their old points stay stored until you annotate them again.

## Export the dataset

Builds the YOLO dataset in `~/visualMusic-output/export/` from annotated images and shows how far you are from the targets of 300 annotated images and 50 frames from your videos. It can run at any time. The dataset and the training results stay outside the project because a cloud-synced folder, such as an iCloud Desktop, can leave duplicate files behind when a folder is rebuilt.

```shell
.venv/bin/python -m dataset_tools.export
```

## Run the trial training

Trains briefly on the exported dataset, then draws the predicted points on the validation images in `~/visualMusic-output/runs/trial/predictions/`. Look at those images: a wrong result on the Apple GPU would not raise an error. This trial proves the pipeline works, not that the model is good. The first run downloads the base model, so it needs network access.

```shell
.venv/bin/python -m dataset_tools.trial
```

## Train the model

Trains for 100 passes on the exported dataset, always starting from the base model, and saves the result as `~/visualMusic-output/runs/latest.pt`. Next to it, `latest.json` records which images the model learned from, the code version and the validation scores. This takes about 30 minutes with 225 images on an M1 Pro, and longer with more. If training fails or you stop it, the previous model stays in use.

```shell
.venv/bin/python -m dataset_tools.train
```

## Prepare the model for publication

Builds `~/visualMusic-output/release/` with everything needed to publish the latest model in compliance with its licenses:

- `visualMusic-saxophone-pose.pt`, the model;
- `README.md`, the model card: what the model does, what it was trained on, its scores, limits, license and a link to the exact source code;
- `CREDITS.md`, every image the model learned from, with its author, link and license. Frames from your videos are only counted, and video names never appear;
- `LICENSE`, the AGPL-3.0 text.

```shell
.venv/bin/python -m dataset_tools.release
```

CC BY 2.0 to 3.0 licenses ask to credit the title the author gave to the image. Images collected before titles were recorded get them with this command, which reads the Open Images metadata again and takes several minutes:

```shell
.venv/bin/python -m dataset_tools.titles
```

The release stops if a CC BY image it would credit has no recorded title, and it stops if the model has no record of its training images, for example a model trained before this command existed: train it again first. Commit the code before training, so that the model card links source code that matches the model. Publish the four files together, for example as a GitHub release or on Hugging Face, after making the repository public and pushing the linked commit.

## Compute the proposals

Uses `~/visualMusic-output/runs/latest.pt` to suggest the points on every image still to be marked, including skipped ones, and shows how many got a suggestion. Run it again after a new training or collection: annotations never change, and an interrupted run keeps what it already computed.

```shell
.venv/bin/python -m dataset_tools.propose
```

Proposals stay in `data/proposals/`, are not versioned, and never reach the exported dataset.

## Track the saxophone live

Starts a page reachable only from this computer, using the latest trained model. Stop it with Ctrl+C.

```shell
.venv/bin/python -m live_tracking.server
```

Choose a camera or a video file. The page draws the points the model is confident about, and highlights in yellow the point where sound leaves the bell: its centre or, when that is hidden, the midpoint of the two edges. Nothing is saved.

With a camera, sound comes from the microphone chosen on the same screen; with a video, from the video's own audio, which you also hear. A small chart in the bottom-right corner shows the volume horizontally and the frequency vertically, from 80 to 1600 Hz, with a trail of the last 2 seconds. A glow lights up on the bell, centred on the yellow point: it grows brighter and larger with the volume, shifts from warm orange in low frequencies to cold blue in high ones, and turns white for breath or key noise. **Nascondi punti** hides the tracked points to see the glow alone. If the microphone is refused or the video has no sound, tracking goes on without the chart and the glow.

To judge the model, film a video it has never seen and open it here. Keep that video out of `data/videos/`, because everything in that folder ends up in training.

## Privacy

The local pages are reachable only from this computer. Camera, microphone and video are processed in the browser and on this computer; nothing is recorded, saved or sent anywhere, and the microphone is turned off when tracking stops. The only network access is downloading images from their public sources, the base model from Ultralytics, and the Python packages during setup.

## Data and attribution

Everything in `data/` stays on your computer and is never part of the repository: images, videos, the manifest `data/manifest.jsonl` and the annotations in `data/annotations/`. Run the tools above to build your own.

Images are collected only under CC0, public domain or CC BY, as declared by each source. The manifest records, for every image, its source, title, author, license and a link to its original page, so the authors can be credited wherever the dataset or a model trained on it is shared. Each image keeps its own license. Sources may occasionally declare a wrong license: if you are the author of an image used to train a published model and want it removed, open an issue and it will be excluded from future trainings.

## Third-party software

| Component | Used for | License |
|-----------|----------|---------|
| [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) and its pretrained pose model | Training and running the model | AGPL-3.0 |
| [PyTorch](https://pytorch.org), [NumPy](https://numpy.org), [OpenCV](https://opencv.org) (installed with Ultralytics) | Computation and video frames | BSD-style / Apache-2.0 |
| [pytest](https://pytest.org) | Tests | MIT |
| [Playwright](https://playwright.dev) | Browser tests | Apache-2.0 |

These packages are installed from PyPI by `scripts/setup.sh` and are not included in the repository.

## Contributing

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright (C) 2026 Carlo Fanelli.

- **Code**: [GNU Affero General Public License v3.0](LICENSE). The project depends on Ultralytics YOLO, licensed under AGPL-3.0, so any distribution of the project, or of a modified version, must keep the same license and provide its source code — including when a modified version is offered to others over a network.
- **Trained models** are produced with Ultralytics YOLO and are distributed under AGPL-3.0, together with their model card and the list of the authors of the images they were trained on, as prepared by `dataset_tools.release`.
