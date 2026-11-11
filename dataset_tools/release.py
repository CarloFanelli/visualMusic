"""Prepares the trained model for publication: the model, its credits, its model card and its license."""
import collections
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from urllib.parse import quote

from dataset_tools import frames, licenses, manifest, paths, titles
from dataset_tools import instrument as instrument_module

REPOSITORY = "https://github.com/CarloFanelli/visualMusic"
MODEL_FILE = "visualMusic-saxophone-pose.pt"
OPEN_IMAGES = "Open Images"
OPEN_IMAGES_URL = "https://storage.googleapis.com/openimages/web/index.html"
CC_BY_4 = "https://creativecommons.org/licenses/by/4.0/"

_CC_URL = re.compile(r"creativecommons\.org/(?:licenses|publicdomain)/([a-z-]+)/(\d\.\d)(?:/([a-z]{2})(?=/|$))?")
_CC_NAMES = {"by": "CC BY", "zero": "CC0", "mark": "Public Domain Mark"}
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#|!~])")


class ReleaseError(Exception):
    pass


@dataclass
class Release:
    directory: object
    images: int = 0
    by_license: dict = field(default_factory=dict)
    user_frames: int = 0
    warnings: list = field(default_factory=list)


def license_link(record):
    """Returns the license's human name and the link to its text, or None when it has no single text."""
    url = record.get("license_url") or ""
    match = _CC_URL.search(url.lower())
    if match:
        terms, version, country = match.groups()
        name = f"{_CC_NAMES.get(terms, 'CC ' + terms.upper())} {version}" + (f" {country.upper()}" if country else "")
        return name, url
    if record.get("license") == licenses.PUBLIC_DOMAIN:
        return "Public domain", None
    if record.get("license") == licenses.CC0:
        return "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"
    return record.get("license_raw") or record.get("license"), None


def _text(value):
    """Author names and titles come from the sources, so they must not be able to break the Markdown."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", " ".join(str(value).split()))


def _url(value):
    return quote(value, safe=":/?&=#%~+,;@!$'*")


def _title(record):
    title = record.get("title")
    if title is None:
        title = titles.commons_title(record)
    return title or "Untitled"


def credit_line(record):
    title = _text(_title(record))
    work = f"[{title}]({_url(record['source_url'])})" if record.get("source_url") else title
    author = _text(record["author"]) if record.get("author") else "author not stated by the source"
    name, url = license_link(record)
    license_text = f"[{_text(name)}]({_url(url)})" if url else _text(name)
    return f"- {work} by {author}, {license_text}, from {_text(record['source'])}"


def _trained_records(info, records_by_file):
    files = [name for split in ("train", "val") for name in info["images"].get(split, [])]
    missing = [name for name in files if name not in records_by_file]
    if missing:
        raise ReleaseError(f"{len(missing)} images used in training are not in the manifest, so their authors cannot be credited: {', '.join(missing[:5])}")
    records = [records_by_file[name] for name in files]
    untitled = [record["image_id"] for record in records if record.get("license") == licenses.CC_BY and record.get("title") is None and titles.commons_title(record) is None]
    if untitled:
        raise ReleaseError(f"{len(untitled)} CC BY images have no recorded title, which their license asks to credit. Run: .venv/bin/python -m dataset_tools.titles")
    return records


def credits_text(records, info):
    online = sorted((record for record in records if record.get("license") != frames.USER_OWNED), key=lambda record: (record["source"], record["image_id"]))
    attributed = [record for record in online if record.get("license") == licenses.CC_BY]
    free = [record for record in online if record.get("license") != licenses.CC_BY]
    user_frames = len(records) - len(online)
    lines = [
        f"# Credits for {MODEL_FILE}",
        "",
        f"This model, trained on {info['trained_on']}, learned from the {len(records)} images listed below. "
        "No image is included in the model or in this release: each one was resized and marked with four points only to train the model.",
        "",
        "Each image stays under its own license, linked below, whose full text includes its disclaimer of warranties. "
        "Titles, authors and licenses are as declared by each source.",
        "",
        f"If you are the author of one of these images and want it removed, open an issue at {REPOSITORY}/issues with its link: it will be left out of future versions of the model.",
    ]
    if attributed:
        lines += ["", f"## CC BY images ({len(attributed)})", "", *map(credit_line, attributed)]
    if free:
        lines += ["", f"## CC0 and public domain images ({len(free)})", "", "Attribution is not required for these images; they are listed for transparency.", "", *map(credit_line, free)]
    if any(record["source"] == OPEN_IMAGES for record in online):
        lines += [
            "",
            "## Open Images",
            "",
            f"Images from Open Images were found through the bounding-box annotations of the [Open Images Dataset]({OPEN_IMAGES_URL}) by Google LLC, "
            f"licensed under [CC BY 4.0]({CC_BY_4}). Those annotations were used only to find saxophone images, and are not part of the training data.",
        ]
    if user_frames:
        lines += ["", "## Frames from the developer's videos", "", f"{user_frames} frames come from videos recorded by the developer, who owns their rights."]
    return "\n".join(lines) + "\n"


def _metrics_text(info):
    metrics = info.get("metrics")
    validation = len(info["images"].get("val", []))
    if not metrics:
        return "No validation scores were recorded for this training."
    return (
        f"On the {validation} validation images, at epoch {metrics['epoch']} (the one with the best point accuracy): "
        f"pose mAP50 {metrics['pose_map50']:.3f}, pose mAP50-95 {metrics['pose_map50_95']:.3f}.\n\n"
        "Many validation images were marked starting from points suggested by an earlier version of the model, "
        "so these scores are probably optimistic. Judge the model on a video it has never seen."
    )


def _source_link(info):
    if info.get("code_commit"):
        return f"[{REPOSITORY}/tree/{info['code_commit']}]({REPOSITORY}/tree/{info['code_commit']})"
    return f"[{REPOSITORY}]({REPOSITORY})"


def model_card(records, info, instrument, model_sha256):
    counts = collections.Counter((record["source"], license_link(record)[0]) for record in records if record.get("license") != frames.USER_OWNED)
    user_frames = sum(1 for record in records if record.get("license") == frames.USER_OWNED)
    data_rows = [f"| {_text(source)} | {_text(name)} | {count} |" for (source, name), count in sorted(counts.items())]
    if user_frames:
        data_rows.append(f"| Developer's own videos | Own work | {user_frames} |")
    points = ", ".join(f"`{name}`" for name in instrument.point_names)
    return f"""---
license: agpl-3.0
library_name: ultralytics
pipeline_tag: keypoint-detection
tags:
- ultralytics
- yolo
- pose
- saxophone
- music
---

# visualMusic saxophone pose model

Finds a saxophone in an image and {len(instrument.point_names)} points on it, so that visual effects can be drawn where the sound leaves the bell. It is the model used by [visualMusic]({REPOSITORY}).

## Model details

- **Developed by**: Carlo Fanelli, as part of visualMusic.
- **Type**: Ultralytics YOLO pose model, one class (`{instrument.class_name}`) with {len(instrument.point_names)} points.
- **Points, in order**: {points}.
- **Base model**: `{info['base_model']}`, pretrained by Ultralytics, then trained on the data below.
- **File**: `{MODEL_FILE}`, SHA-256 `{model_sha256}`.
- **Trained on**: {info['trained_on']}.
- **Source code**: {_source_link(info)}.
- **License**: [GNU Affero General Public License v3.0](LICENSE).

## Intended use

Following a saxophone live, from a camera or a video, on the user's own computer, to place visual effects driven by the instrument's sound.

```python
from ultralytics import YOLO

model = YOLO("{MODEL_FILE}")
result = model.predict("photo.jpg")[0]
print(result.keypoints.xy)
```

## Out-of-scope use

- Identifying, recognising or following people: the model only locates an instrument, and must not be used, alone or with other models, to monitor people.
- Any decision with legal or similarly significant effects on people.
- Instruments it was not trained on: it learned mostly from tenor and alto saxophones, while soprano saxophones and images with several saxophones were left out, so results on them are unreliable.

## Training data

| Source | License | Images |
|--------|---------|--------|
{chr(10).join(data_rows)}

- Online images were collected only under CC0, public domain or CC BY licenses, as declared by each source. Every image and its author is listed in [CREDITS.md](CREDITS.md).
- The points were marked by hand by the developer, sometimes starting from points suggested by an earlier version of the model and then checked.
- Neither the images nor the annotations are part of this release. The images can be found through the links in the credits, under their own licenses.
- {len(info['images'].get('train', []))} images were used for training and {len(info['images'].get('val', []))} for validation. The split is fixed per image, and all frames of one video stay on the same side.

## Training procedure

{info['epochs']} epochs at an image size of {info['image_size']} pixels, starting from the base model, with the default settings of Ultralytics. The code that collects the images, exports the dataset and trains the model is in the source code linked above.

## Evaluation

{_metrics_text(info)}

## Limitations and risks

- The dataset is small: lighting, unusual angles, stage lights and hands covering the bell can make points wrong or missing.
- Licenses are those declared by the sources, which can occasionally be wrong. See removal requests below.
- Points can be wrong without any warning. Do not rely on them where a mistake could cause harm.

## Personal data

Some training photos show musicians. The model was trained only to locate the instrument: its output is a box and {len(instrument.point_names)} points, with nothing about people. No image is included in the model or in this release. visualMusic runs the model locally: camera, microphone and video are never sent anywhere.

## License and source code

Copyright (C) 2026 Carlo Fanelli.

This model is a modified version of `{info['base_model']}` by Ultralytics, licensed under AGPL-3.0: it was modified by training it on the data above, on {info['trained_on']}.

The model is distributed under the [GNU Affero General Public License v3.0](LICENSE), because it was trained with Ultralytics YOLO, which is licensed under AGPL-3.0. Anyone who distributes this model or a modified version, or offers it to others over a network, must do so under the same license and provide the corresponding source code.

The image authors are credited in [CREDITS.md](CREDITS.md), which must accompany every copy of the model.

## Removal requests

If you are the author of an image used for training and want it removed, open an issue at {REPOSITORY}/issues with its link: it will be left out of future versions of the model.

## No warranty

The model is provided "as is", without warranty of any kind, as stated in sections 15 and 16 of the license.
"""


def run(model_path=paths.LATEST_MODEL, info_path=paths.LATEST_INFO, manifest_path=paths.MANIFEST, release_dir=paths.RELEASE, instrument=None, license_path=paths.ROOT / "LICENSE"):
    if not model_path.exists():
        raise ReleaseError("No trained model found. Run: .venv/bin/python -m dataset_tools.train")
    if not info_path.exists():
        raise ReleaseError("The model has no record of the images it was trained on, so their authors cannot be credited. Train it again: .venv/bin/python -m dataset_tools.train")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if info.get("model_sha256") != model_sha256:
        raise ReleaseError("The model does not match the record of its training. Train it again: .venv/bin/python -m dataset_tools.train")
    records = _trained_records(info, {record["file"]: record for record in manifest.load(manifest_path, repair=False)})
    instrument = instrument or instrument_module.load()

    release = Release(release_dir, images=len(records))
    release.user_frames = sum(1 for record in records if record.get("license") == frames.USER_OWNED)
    release.by_license = dict(collections.Counter(record["license"] for record in records))
    if not info.get("code_commit"):
        release.warnings.append("The training was not done in a git repository, so the model card cannot link the exact source code.")
    elif info.get("code_changed"):
        release.warnings.append("The training code had changes not yet committed, so the linked source code may not match the model. Commit them and train again.")

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    shutil.copyfile(model_path, release_dir / MODEL_FILE)
    shutil.copyfile(license_path, release_dir / "LICENSE")
    (release_dir / "CREDITS.md").write_text(credits_text(records, info), encoding="utf-8")
    (release_dir / "README.md").write_text(model_card(records, info, instrument, model_sha256), encoding="utf-8")
    return release


def main():
    try:
        release = run()
    except (ReleaseError, manifest.CorruptManifest, instrument_module.InvalidInstrument, OSError, ValueError) as error:
        print(f"Release stopped: {error}")
        return 1
    print(f"Release prepared in {release.directory}: the model, README.md (the model card), CREDITS.md and LICENSE.")
    print(f"Images credited: {release.images}, of which {release.user_frames} frames from your videos.")
    for warning in release.warnings:
        print(f"WARNING: {warning}")
    print("Before publishing: make the repository public, push the commit linked in the model card, and upload all four files together.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
