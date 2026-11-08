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

Starts a page reachable only from this computer. Click the requested points in order: each image saves automatically and the next one opens. Stop with Ctrl+C at any time and start again later to resume.

```shell
.venv/bin/python -m dataset_tools.annotate.server
```

Use **Annulla** to remove the last point, **Punto non visibile** for a hidden point, **Salta** to postpone an image, and **Non adatta** to discard it, for example a soprano, several saxophones or no saxophone. A discarded image can be restored by opening it from the list.

Point names and their order are in `instruments/saxophone.json`. If you change them, images already annotated return to pending, and their old points stay stored until you annotate them again.

## Export the dataset

Builds the YOLO dataset in `data/export/` from annotated images and shows how far you are from the targets of 300 annotated images and 50 frames from your videos. It can run at any time.

```shell
.venv/bin/python -m dataset_tools.export
```

## Run the trial training

Trains briefly on the exported dataset, then draws the predicted points on the validation images in `runs/trial/predictions/`. Look at those images: a wrong result on the Apple GPU would not raise an error. This trial proves the pipeline works, not that the model is good. The first run downloads the base model, so it needs network access.

```shell
.venv/bin/python -m dataset_tools.trial
```

## Data in git

The manifest and annotations are versioned. Image and video files are not.

## License note

This project trains models with Ultralytics YOLO, licensed under AGPL-3.0. If the project is distributed or offered online, its code must be released under the same license.
