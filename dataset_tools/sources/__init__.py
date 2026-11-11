from dataclasses import dataclass
from typing import Optional


@dataclass
class Candidate:
    image_id: str
    source: str
    source_url: str
    download_url: str
    author: Optional[str]
    license_raw: Optional[str]
    license_url: Optional[str]
    # The title the author gave, needed to credit CC BY 2.0 to 3.0 images; empty when none was given.
    title: Optional[str] = None
    # Set when the source itself shows the file cannot be used.
    unsupported_reason: Optional[str] = None
