# visualMusic

Tracks the point where sound leaves a musical instrument, starting with the saxophone.

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

Trains for 100 passes on the exported dataset, always starting from the base model, and saves the result as `~/visualMusic-output/runs/latest.pt`. This takes about 30 minutes with 225 images on an M1 Pro, and longer with more. If training fails or you stop it, the previous model stays in use.

```shell
.venv/bin/python -m dataset_tools.train
```

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

To judge the model, film a video it has never seen and open it here. Keep that video out of `data/videos/`, because everything in that folder ends up in training.

## Data in git

The manifest and annotations are versioned. Image and video files are not.

## License note

This project trains models with Ultralytics YOLO, licensed under AGPL-3.0. If the project is distributed or offered online, its code must be released under the same license.
