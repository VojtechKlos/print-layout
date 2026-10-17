"""Loading photos: downscaled copies for the screen, full resolution for output."""

from __future__ import annotations

import functools
import os
import re
from collections import OrderedDict
from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader

_COMMON_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "gif", "heic", "heif", "avif")


@functools.cache
def image_extensions() -> tuple[str, ...]:
    """Common photo extensions that this Qt build can actually read."""
    supported = {bytes(f.data()).decode().lower() for f in QImageReader.supportedImageFormats()}
    return tuple(ext for ext in _COMMON_EXTENSIONS if ext in supported)


def is_image_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower().lstrip(".") in image_extensions()


def _natural_key(name: str) -> list[int | str]:
    # "IMG_2" sorts before "IMG_10".
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]


def collect_image_paths(paths: Iterable[str]) -> list[str]:
    """Readable images among `paths`; a folder contributes its own images (not subfolders)."""
    result: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            names = sorted(os.listdir(path), key=_natural_key)
            result += [
                os.path.join(path, name)
                for name in names
                if is_image_path(name) and os.path.isfile(os.path.join(path, name))
            ]
        elif is_image_path(path):
            result.append(path)
    return result


def load_image(path: str, max_side: int | None = None) -> QImage | None:
    """Read an image upright (EXIF orientation applied), optionally downscaled while decoding."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if max_side:
        size = reader.size()
        if size.isValid() and max(size.width(), size.height()) > max_side:
            reader.setScaledSize(size.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    return None if image.isNull() else image


class ImageCache:
    """LRU cache of downscaled photos for the on-screen preview."""

    def __init__(self, max_side: int = 1600, max_bytes: int = 256 * 1024 * 1024):
        self._max_side = max_side
        self._max_bytes = max_bytes
        self._bytes = 0
        self._images: OrderedDict[str, QImage | None] = OrderedDict()

    def get(self, path: str) -> QImage | None:
        if path in self._images:
            self._images.move_to_end(path)
            return self._images[path]
        image = load_image(path, self._max_side)
        self._images[path] = image
        self._bytes += image.sizeInBytes() if image else 0
        while self._bytes > self._max_bytes and len(self._images) > 1:
            _, old = self._images.popitem(last=False)
            self._bytes -= old.sizeInBytes() if old else 0
        return image

    def forget(self, path: str) -> None:
        image = self._images.pop(path, None)
        self._bytes -= image.sizeInBytes() if image else 0
