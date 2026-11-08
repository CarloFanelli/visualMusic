"""Fetches an image and only puts it in place once it is complete and valid."""
import os

from PIL import Image

# MPO is a JPEG carrying extra pictures, as some cameras write them.
EXTENSIONS = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png"}


class UnsupportedImage(Exception):
    pass


def extension_of(path):
    try:
        with Image.open(path) as image:
            image_format = image.format
            image.verify()
    except Exception as error:  # Pillow raises many types for damaged files
        raise UnsupportedImage(f"not a readable image: {error}") from error
    if image_format not in EXTENSIONS:
        raise UnsupportedImage(f"unsupported format: {image_format}")
    return EXTENSIONS[image_format]


def fetch(http, url, directory, image_id):
    """Returns (file name, SHA-256). Leaves nothing behind when it fails."""
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{image_id}.part"
    try:
        sha256 = http.download(url, temporary)
        file_name = f"{image_id}.{extension_of(temporary)}"
        os.replace(temporary, directory / file_name)
        return file_name, sha256
    finally:
        temporary.unlink(missing_ok=True)
