import hashlib
import json

import pytest

from dataset_tools import manifest, release
from dataset_tools import instrument as instrument_module

SAX = instrument_module.load()
RUN = release.run
MODEL = b"trained model"

COMMONS = {
    "image_id": "commons-1",
    "source": "Wikimedia Commons",
    "source_url": "https://commons.wikimedia.org/wiki/File:Tenor_sax_(live).jpg",
    "author": "Jane [Doe]",
    "license": "cc-by",
    "license_raw": "CC BY 2.5 ca",
    "license_url": "https://creativecommons.org/licenses/by/2.5/ca/deed.en",
    "file": "commons-1.jpg",
}
OPEN_IMAGES = {
    "image_id": "openimages-2",
    "source": "Open Images",
    "source_url": "https://www.flickr.com/photos/someone/2",
    "author": "Someone",
    "title": "Late set",
    "license": "cc-by",
    "license_raw": "https://creativecommons.org/licenses/by/2.0/",
    "license_url": "https://creativecommons.org/licenses/by/2.0/",
    "file": "openimages-2.jpg",
}
PUBLIC_DOMAIN = {
    "image_id": "commons-3",
    "source": "Wikimedia Commons",
    "source_url": "https://commons.wikimedia.org/wiki/File:Old_sax.jpg",
    "author": "Unknown photographer",
    "license": "public-domain",
    "license_raw": "Public domain",
    "license_url": "https://commons.wikimedia.org/wiki/File:Old_sax.jpg",
    "file": "commons-3.jpg",
}
USER_FRAME = {
    "image_id": "video-abc-00001000",
    "source": "user-video",
    "source_url": None,
    "author": "project owner",
    "license": "user-owned",
    "license_raw": None,
    "license_url": None,
    "file": "video-abc-00001000.jpg",
    "video_id": "abc",
    "video_file": "Private family clip.mov",
}
NOT_TRAINED = {**OPEN_IMAGES, "image_id": "openimages-9", "author": "Never Used", "file": "openimages-9.jpg"}


@pytest.fixture
def workspace(tmp_path):
    class Workspace:
        model = tmp_path / "latest.pt"
        info = tmp_path / "latest.json"
        manifest_path = tmp_path / "manifest.jsonl"
        release_dir = tmp_path / "release"
        license_path = tmp_path / "LICENSE"

        def train(self, train_files, val_files, **extra):
            self.model.write_bytes(MODEL)
            record = {
                "model_sha256": hashlib.sha256(MODEL).hexdigest(),
                "trained_on": "2026-11-11",
                "base_model": "yolo26n-pose.pt",
                "epochs": 100,
                "image_size": 640,
                "images": {"train": train_files, "val": val_files},
                "code_commit": "abc123",
                "code_changed": False,
                "metrics": {"epoch": 72, "pose_map50": 0.93124, "pose_map50_95": 0.87296},
            }
            record.update(extra)
            self.info.write_text(json.dumps(record))

        def run(self):
            return RUN(self.model, self.info, self.manifest_path, self.release_dir, SAX, self.license_path)

        def read(self, name):
            return (self.release_dir / name).read_text(encoding="utf-8")

    workspace = Workspace()
    workspace.license_path.write_text("AGPL text")
    for record in (COMMONS, OPEN_IMAGES, PUBLIC_DOMAIN, USER_FRAME, NOT_TRAINED):
        manifest.append(record, workspace.manifest_path)
    return workspace


def train_all(workspace, **extra):
    workspace.train([COMMONS["file"], OPEN_IMAGES["file"], USER_FRAME["file"]], [PUBLIC_DOMAIN["file"]], **extra)


def test_release_holds_the_model_its_card_its_credits_and_the_license(workspace):
    train_all(workspace)
    workspace.run()
    assert sorted(path.name for path in workspace.release_dir.iterdir()) == ["CREDITS.md", "LICENSE", "README.md", release.MODEL_FILE]
    assert (workspace.release_dir / release.MODEL_FILE).read_bytes() == MODEL
    assert workspace.read("LICENSE") == "AGPL text"


def test_credits_name_every_trained_image_with_author_link_and_license(workspace):
    train_all(workspace)
    workspace.run()
    credits = workspace.read("CREDITS.md")
    assert "Jane \\[Doe\\]" in credits
    assert "[CC BY 2.5 CA](https://creativecommons.org/licenses/by/2.5/ca/deed.en)" in credits
    assert "(https://commons.wikimedia.org/wiki/File:Tenor_sax_%28live%29.jpg)" in credits
    assert "[CC BY 2.0](https://creativecommons.org/licenses/by/2.0/)" in credits
    assert "Unknown photographer, Public domain" in credits
    assert "[Late set](https://www.flickr.com/photos/someone/2)" in credits
    assert "[Tenor sax \\(live\\).jpg]" in credits


def test_an_image_whose_author_gave_no_title_is_credited_as_untitled(workspace):
    manifest.rewrite([{**record, "title": ""} for record in manifest.load(workspace.manifest_path)], workspace.manifest_path)
    train_all(workspace)
    workspace.run()
    assert "[Untitled](https://www.flickr.com/photos/someone/2)" in workspace.read("CREDITS.md")


def test_cc_by_image_with_an_unknown_title_stops_and_names_the_titles_command(workspace):
    manifest.append({**OPEN_IMAGES, "image_id": "openimages-5", "file": "openimages-5.jpg", "title": None}, workspace.manifest_path)
    workspace.train(["openimages-5.jpg"], [])
    with pytest.raises(release.ReleaseError, match="dataset_tools.titles"):
        workspace.run()


def test_credits_leave_out_images_the_model_never_saw(workspace):
    train_all(workspace)
    workspace.run()
    assert "Never Used" not in workspace.read("CREDITS.md")


def test_credits_count_the_developer_frames_without_naming_the_videos(workspace):
    train_all(workspace)
    report = workspace.run()
    credits = workspace.read("CREDITS.md") + workspace.read("README.md")
    assert "1 frames come from videos recorded by the developer" in credits
    assert "Private family clip" not in credits
    assert "video-abc" not in credits
    assert report.user_frames == 1


def test_credits_credit_the_open_images_annotations_when_used(workspace):
    train_all(workspace)
    workspace.run()
    assert "Google LLC" in workspace.read("CREDITS.md")


def test_credits_skip_open_images_when_not_used(workspace):
    workspace.train([COMMONS["file"]], [PUBLIC_DOMAIN["file"]])
    workspace.run()
    assert "Google LLC" not in workspace.read("CREDITS.md")


def test_model_card_states_license_source_data_and_scores(workspace):
    train_all(workspace)
    workspace.run()
    card = workspace.read("README.md")
    assert card.startswith("---\nlicense: agpl-3.0\n")
    assert f"{release.REPOSITORY}/tree/abc123" in card
    assert hashlib.sha256(MODEL).hexdigest() in card
    assert "| Wikimedia Commons | CC BY 2.5 CA | 1 |" in card
    assert "| Developer's own videos | Own work | 1 |" in card
    assert "3 images were used for training and 1 for validation" in card
    assert "pose mAP50 0.931, pose mAP50-95 0.873" in card
    assert ", ".join(f"`{name}`" for name in SAX.point_names) in card
    assert "Copyright (C) 2026 Carlo Fanelli" in card
    assert "modified version of `yolo26n-pose.pt` by Ultralytics" in card


def test_model_card_says_when_there_are_no_scores(workspace):
    train_all(workspace, metrics=None)
    workspace.run()
    assert "No validation scores were recorded" in workspace.read("README.md")


def test_uncommitted_training_code_is_a_warning(workspace):
    train_all(workspace, code_changed=True)
    assert any("not yet committed" in warning for warning in workspace.run().warnings)


def test_missing_model_stops_and_names_the_training_command(workspace):
    with pytest.raises(release.ReleaseError, match="dataset_tools.train"):
        workspace.run()


def test_model_without_a_training_record_stops(workspace):
    workspace.model.write_bytes(MODEL)
    with pytest.raises(release.ReleaseError, match="Train it again"):
        workspace.run()
    assert not workspace.release_dir.exists()


def test_model_that_does_not_match_its_record_stops(workspace):
    train_all(workspace)
    workspace.model.write_bytes(b"another model")
    with pytest.raises(release.ReleaseError, match="does not match"):
        workspace.run()


def test_trained_image_missing_from_the_manifest_stops(workspace):
    workspace.train(["lost.jpg"], [])
    with pytest.raises(release.ReleaseError, match="lost.jpg"):
        workspace.run()


def test_a_new_release_replaces_the_previous_one(workspace):
    workspace.release_dir.mkdir()
    (workspace.release_dir / "old.txt").write_text("old")
    train_all(workspace)
    workspace.run()
    assert not (workspace.release_dir / "old.txt").exists()


@pytest.mark.parametrize(
    "record, expected",
    [
        ({"license": "cc-by", "license_url": "https://creativecommons.org/licenses/by/4.0/"}, ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")),
        ({"license": "cc0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"}, ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/")),
        ({"license": "public-domain", "license_url": "https://creativecommons.org/publicdomain/mark/1.0/"}, ("Public Domain Mark 1.0", "https://creativecommons.org/publicdomain/mark/1.0/")),
        ({"license": "public-domain", "license_url": "https://commons.wikimedia.org/wiki/File:x.jpg"}, ("Public domain", None)),
        ({"license": "cc0", "license_url": "http://creativecommons.org/publicdomain/zero/1.0/deed.en"}, ("CC0 1.0", "http://creativecommons.org/publicdomain/zero/1.0/deed.en")),
        ({"license": "cc-by", "license_url": "https://creativecommons.org/licenses/by/2.5/se"}, ("CC BY 2.5 SE", "https://creativecommons.org/licenses/by/2.5/se")),
        ({"license": "cc0", "license_url": None}, ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/")),
    ],
)
def test_license_names_and_links(record, expected):
    assert release.license_link(record) == expected


def test_command_reports_the_release_and_its_warnings(workspace, monkeypatch, capsys):
    train_all(workspace, code_changed=True)
    monkeypatch.setattr(release, "run", lambda: workspace.run())
    assert release.main() == 0
    output = capsys.readouterr().out
    assert str(workspace.release_dir) in output
    assert "WARNING" in output


def test_command_explains_a_stop_and_fails(workspace, monkeypatch, capsys):
    monkeypatch.setattr(release, "run", lambda: workspace.run())
    assert release.main() == 1
    assert "Release stopped" in capsys.readouterr().out
