from dataset_tools import manifest, titles
from dataset_tools.http_client import RequestFailed
from dataset_tools.sources import open_images

COMMONS = {"image_id": "commons-1", "source": "Wikimedia Commons", "source_url": "https://commons.wikimedia.org/wiki/File:Tenor_sax_%28live%29.jpg"}
OPEN_IMAGES = {"image_id": "openimages-s0", "source": "Open Images", "source_url": "https://flickr.example/1"}
OPEN_IMAGES_UNTITLED = {"image_id": "openimages-s1", "source": "Open Images", "source_url": "https://flickr.example/2"}
OPEN_IMAGES_GONE = {"image_id": "openimages-gone", "source": "Open Images", "source_url": "https://flickr.example/3"}
OPENVERSE = {"image_id": "openverse-abc", "source": "Openverse", "source_url": "https://flickr.example/4"}
USER_FRAME = {"image_id": "video-1", "source": "user-video", "source_url": None}
ALREADY_TITLED = {"image_id": "openverse-old", "source": "Openverse", "source_url": "x", "title": "Kept"}


class FakeHttp:
    def __init__(self, openverse_titles=None, csv_fails=False):
        self.openverse_titles = openverse_titles or {}
        self.csv_fails = csv_fails
        self.json_requests = []

    def iter_csv_rows(self, url):
        if self.csv_fails:
            raise RequestFailed("metadata down")
        for annotations_url, metadata_url in open_images.SPLITS:
            if url == annotations_url:
                return iter([{"ImageID": "s0", "LabelName": open_images.SAXOPHONE_LABEL}, {"ImageID": "s1", "LabelName": open_images.SAXOPHONE_LABEL}])
            if url == metadata_url:
                return iter([
                    {"ImageID": "s0", "Subset": "train", "OriginalLandingURL": "u", "License": "l", "Author": "Ann", "Title": "Night gig "},
                    {"ImageID": "s1", "Subset": "train", "OriginalLandingURL": "u", "License": "l", "Author": "Bo", "Title": ""},
                ])
        return iter([])

    def get_json(self, url, params=None):
        self.json_requests.append(url)
        title = self.openverse_titles.get(url)
        if isinstance(title, Exception):
            raise title
        return {"title": title}


def write(path, *records):
    for record in records:
        manifest.append(record, path)


def titles_by_id(path):
    return {record["image_id"]: record.get("title") for record in manifest.load(path)}


def test_titles_are_added_from_each_source(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, COMMONS, OPEN_IMAGES, OPEN_IMAGES_UNTITLED, OPENVERSE, USER_FRAME)
    http = FakeHttp({f"{titles.openverse.API}abc/": "Tenor"})

    report = titles.backfill(http, path, tmp_path / "cache")

    assert titles_by_id(path) == {
        "commons-1": "Tenor sax (live).jpg",
        "openimages-s0": "Night gig",
        "openimages-s1": "",
        "openverse-abc": "Tenor",
        "video-1": None,
    }
    assert report.added == 4


def test_existing_titles_are_left_alone_and_not_asked_again(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, ALREADY_TITLED)
    http = FakeHttp()
    assert titles.backfill(http, path, tmp_path / "cache").added == 0
    assert http.json_requests == []
    assert titles_by_id(path) == {"openverse-old": "Kept"}


def test_open_images_cache_is_refreshed_with_titles(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, OPEN_IMAGES)
    titles.backfill(FakeHttp(), path, tmp_path / "cache")
    candidate = next(open_images.candidates(FakeHttp(csv_fails=True), [], tmp_path / "cache"))
    assert candidate.title == "Night gig"


def test_image_no_longer_at_the_source_is_reported(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, OPEN_IMAGES_GONE)
    report = titles.backfill(FakeHttp(), path, tmp_path / "cache")
    assert report.not_found == ["openimages-gone"]
    assert titles_by_id(path) == {"openimages-gone": None}


def test_unreachable_source_keeps_the_manifest_and_is_reported(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, OPEN_IMAGES, OPENVERSE)
    before = path.read_bytes()
    http = FakeHttp({f"{titles.openverse.API}abc/": RequestFailed("down")}, csv_fails=True)
    report = titles.backfill(http, path, tmp_path / "cache")
    assert len(report.failures) == 2
    assert path.read_bytes() == before
    assert any("FAILED" in line for line in report.lines())


def test_manifest_rewrite_replaces_all_records(tmp_path):
    path = tmp_path / "manifest.jsonl"
    write(path, COMMONS, OPENVERSE)
    manifest.rewrite([{**COMMONS, "title": "x"}], path)
    assert manifest.load(path) == [{**COMMONS, "title": "x"}]
    assert [item.name for item in tmp_path.iterdir()] == ["manifest.jsonl"]
