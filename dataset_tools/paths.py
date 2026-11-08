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
EXPORT = DATA / "export"
PROPOSALS = DATA / "proposals"
RUNS = ROOT / "runs"
LATEST_MODEL = RUNS / "latest.pt"
