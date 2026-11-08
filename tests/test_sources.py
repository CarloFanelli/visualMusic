from dataset_tools.http_client import RequestFailed
from dataset_tools.sources import commons, open_images, openverse


class FakeHttp:
    def __init__(self, json_responses=None, csv_rows=None):
        self.json_responses = list(json_responses or [])
        self.csv_rows = csv_rows or {}
        self.csv_requests = 0

    def get_json(self, url, params=None):
        response = self.json_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def iter_csv_rows(self, url):
        self.csv_requests += 1
        return iter(self.csv_rows.get(url, []))


def commons_page(pageid, title, mime="image/jpeg", license_name="CC BY 4.0", artist='<a href="//x">Ann Lee</a>'):
    return {
        "pageid": pageid,
        "title": title,
        "imageinfo": [
            {
                "url": f"https://upload.example/{pageid}.jpg?utm_source=commons",
                "descriptionurl": f"https://commons.example/{pageid}",
                "mime": mime,
                "extmetadata": {
                    "LicenseShortName": {"value": license_name},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0"},
                    "Artist": {"value": artist},
                },
            }
        ],
    }


def test_commons_strips_author_markup_and_flags_audio_files():
    audio = commons_page(2, "File:Sax.ogg", mime="application/ogg")
    http = FakeHttp([{"query": {"pages": {"1": commons_page(1, "File:Sax.jpg"), "2": audio}}}, {}])

    photo, sound = list(commons.candidates(http, []))

    assert photo.author == "Ann Lee"
    assert photo.download_url == "https://upload.example/1.jpg"
    assert photo.unsupported_reason is None
    assert sound.unsupported_reason == "unsupported-format"


def test_commons_treats_unknown_author_as_missing():
    assert commons.author_from_html("Unknown author") is None
    assert commons.author_from_html("") is None


def test_commons_follows_subcategories_once_and_continuation():
    subcategory = {"pageid": 9, "title": "Category:Tenor players"}
    http = FakeHttp(
        [
            {"query": {"pages": {"9": subcategory}}, "continue": {"gcmcontinue": "next"}},
            {"query": {"pages": {"1": commons_page(1, "File:In subcategory.jpg")}}},
            {"query": {"pages": {"2": commons_page(2, "File:After continuation.jpg")}}},
            {"query": {"pages": {"1": commons_page(1, "File:Seen again.jpg")}}},
        ]
    )
    assert [c.image_id for c in commons.candidates(http, [])] == ["commons-1", "commons-2"]


def open_images_http():
    rows = {}
    for number, (annotations_url, metadata_url) in enumerate(open_images.SPLITS):
        rows[annotations_url] = [{"ImageID": f"s{number}", "LabelName": open_images.SAXOPHONE_LABEL}, {"ImageID": "other", "LabelName": "/m/x"}]
        rows[metadata_url] = [
            {"ImageID": f"s{number}", "Subset": "train", "OriginalLandingURL": "https://flickr.example/1", "License": "https://creativecommons.org/licenses/by/2.0/", "Author": "Ann"},
            {"ImageID": "other", "Subset": "train", "OriginalLandingURL": "x", "License": "x", "Author": "x"},
        ]
    return FakeHttp(csv_rows=rows)


def test_open_images_keeps_only_saxophones(tmp_path):
    found = list(open_images.candidates(open_images_http(), [], tmp_path))
    assert [c.image_id for c in found] == ["openimages-s0", "openimages-s1", "openimages-s2"]
    assert found[0].download_url == "https://s3.amazonaws.com/open-images-dataset/train/s0.jpg"
    assert found[0].author == "Ann"


def test_open_images_second_run_downloads_no_csv(tmp_path):
    list(open_images.candidates(open_images_http(), [], tmp_path))
    second_run = FakeHttp()
    assert len(list(open_images.candidates(second_run, [], tmp_path))) == 3
    assert second_run.csv_requests == 0


def test_open_images_failed_download_leaves_no_cache(tmp_path):
    class Failing(FakeHttp):
        def iter_csv_rows(self, url):
            raise RequestFailed("down")

    try:
        list(open_images.candidates(Failing(), [], tmp_path))
    except RequestFailed:
        pass
    assert list(tmp_path.iterdir()) == []


def openverse_result(result_id, license_name="by"):
    return {"id": result_id, "url": f"https://img.example/{result_id}.jpg", "foreign_landing_url": "https://page.example", "creator": "Ann", "license": license_name, "license_url": "https://creativecommons.org/licenses/by/2.0/"}


def test_openverse_stops_at_the_anonymous_limit_and_reports_it():
    page = {"results": [openverse_result("a")], "page_count": 99}
    http = FakeHttp([page] * 12 + [{"results": [], "page_count": 0}])
    notes = []
    assert [c.image_id for c in openverse.candidates(http, notes)] == ["openverse-a"]
    assert any("anonymous limit" in note for note in notes)


def test_openverse_depth_error_ends_the_search_cleanly():
    error = RequestFailed("HTTP 401: pagination depth may not exceed 240 for anonymous requests")
    http = FakeHttp([{"results": [openverse_result("a")], "page_count": 99}, error, {"results": [], "page_count": 0}])
    notes = []
    assert [c.image_id for c in openverse.candidates(http, notes)] == ["openverse-a"]
    assert any("anonymous limit" in note for note in notes)


def test_openverse_says_rejected_licenses_are_filtered_at_source():
    notes = []
    list(openverse.candidates(FakeHttp([{"results": [], "page_count": 0}, {"results": [], "page_count": 0}]), notes))
    assert any("filtered by Openverse" in note for note in notes)


def test_author_ending_in_an_unfinished_entity_is_kept():
    assert commons.author_from_html("AT&T") == "AT&T"
