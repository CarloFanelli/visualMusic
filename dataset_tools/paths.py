"""Single source of truth for project data locations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Versioned in git.
MANIFEST = DATA / "manifest.jsonl"
ANNOTATIONS = DATA / "annotations"
INSTRUMENTS = ROOT / "instruments"

# Local only, ignored by git.
IMAGES = DATA / "images"
VIDEOS = DATA / "videos"
PREVIEWS = DATA / "previews"
CACHE = DATA / "cache"
PROPOSALS = DATA / "proposals"

# Generated and rebuilt often, so kept away from folders that a cloud service syncs.
OUTPUT = Path.home() / "visualMusic-output"
EXPORT = OUTPUT / "export"
RUNS = OUTPUT / "runs"
LATEST_MODEL = RUNS / "latest.pt"
# What the latest model was trained on, needed to credit image authors when it is published.
LATEST_INFO = RUNS / "latest.json"
RELEASE = OUTPUT / "release"
