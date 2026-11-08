import pytest

from dataset_tools import licenses


@pytest.mark.parametrize(
    "raw, family",
    [
        ("CC0", licenses.CC0),
        ("cc0", licenses.CC0),
        ("Public domain", licenses.PUBLIC_DOMAIN),
        ("pdm", licenses.PUBLIC_DOMAIN),
        ("CC BY 2.0", licenses.CC_BY),
        ("CC BY 2.5 ca", licenses.CC_BY),
        ("CC BY 4.0", licenses.CC_BY),
        ("by", licenses.CC_BY),
        ("https://creativecommons.org/licenses/by/2.0/", licenses.CC_BY),
        ("https://creativecommons.org/publicdomain/zero/1.0/", licenses.CC0),
        ("https://creativecommons.org/publicdomain/mark/1.0/", licenses.PUBLIC_DOMAIN),
    ],
)
def test_allowed_licenses(raw, family):
    assert licenses.classify(raw) == (family, None)


@pytest.mark.parametrize(
    "raw, reason",
    [
        (None, "missing-license"),
        ("", "missing-license"),
        ("CC BY-SA 4.0", "share-alike"),
        ("CC BY-SA 3.0 de", "share-alike"),
        ("by-sa", "share-alike"),
        ("https://creativecommons.org/licenses/by-sa/4.0", "share-alike"),
        ("CC BY-NC 2.0", "non-commercial"),
        ("CC BY-NC-SA 4.0", "non-commercial"),
        ("by-nc", "non-commercial"),
        ("https://creativecommons.org/licenses/by-nc-nd/2.0/", "non-commercial"),
        ("CC BY-ND 4.0", "no-derivatives"),
        ("by-nd", "no-derivatives"),
        ("GPL", "gpl"),
        ("GFDL", "gfdl"),
        ("Attribution", "unrecognised"),
        ("All rights reserved", "unrecognised"),
    ],
)
def test_rejected_licenses(raw, reason):
    assert licenses.classify(raw) == (None, reason)


@pytest.mark.parametrize("raw", ["CC BY SA 4.0", "CC BY NC 4.0", "CC BY ND 4.0", "CC BY 4.0 NC", "cc by nc-nd"])
def test_license_terms_written_with_spaces_are_not_plain_cc_by(raw):
    assert licenses.classify(raw) == (None, "unrecognised")
