"""Allowlist of image licenses. Anything not recognised as allowed is rejected."""
import re

CC0 = "cc0"
PUBLIC_DOMAIN = "public-domain"
CC_BY = "cc-by"

# The optional two letters are a country code, which must not be mistaken for license terms.
_CC_BY_NAME = re.compile(r"^cc by \d(\.\d)?( (?!nc$|nd$|sa$)[a-z]{2})?$")
_CC0_NAME = re.compile(r"^cc0( \d(\.\d)?)?$")
_LICENSE_URL = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)")


def _classify_cc_terms(terms):
    if terms == "by":
        return CC_BY, None
    if terms == "zero" or terms == "cc0":
        return CC0, None
    if terms in {"mark", "pdm"}:
        return PUBLIC_DOMAIN, None
    if "nc" in terms.split("-"):
        return None, "non-commercial"
    if "nd" in terms.split("-"):
        return None, "no-derivatives"
    if "sa" in terms.split("-"):
        return None, "share-alike"
    return None, "unrecognised"


def classify(raw):
    """Returns (license family, None) when allowed, or (None, rejection reason)."""
    value = (raw or "").strip().lower()
    if not value:
        return None, "missing-license"

    url = _LICENSE_URL.search(value)
    if url:
        return _classify_cc_terms(url.group(2))

    if _CC_BY_NAME.match(value):
        return CC_BY, None
    if _CC0_NAME.match(value):
        return CC0, None
    if value == "public domain":
        return PUBLIC_DOMAIN, None
    if value.startswith("cc by-"):
        return _classify_cc_terms(value.split()[1])
    if value in {"by", "cc0", "pdm", "by-sa", "by-nc", "by-nd", "by-nc-sa", "by-nc-nd"}:
        return _classify_cc_terms(value)
    if "gfdl" in value:
        return None, "gfdl"
    if "gpl" in value:
        return None, "gpl"
    return None, "unrecognised"
