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
    # Set when the source itself shows the file cannot be used.
    unsupported_reason: Optional[str] = None
