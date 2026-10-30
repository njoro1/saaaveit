"""Download and cache video thumbnails on a worker thread.

The frozen build does not ship QtNetwork or TLS QML plugins, so QML must never
load a remote image. This module turns the thumbnail URL from inspection into a
local ``file:///`` URL under the app's cache directory. Failures are silent by
design: a missing thumbnail is decorative, never an error the user must see.

The cached image is centre-cropped to 16:9, capped at 640 px wide, and has its
corners rounded with transparency. QML's ``clip`` is rectangular, so rounding
at cache time is what lets the preview sit in a rounded card without square
corners poking out.
"""
from __future__ import annotations

import os
import re
import tempfile
import urllib.request

from PySide6.QtCore import QRectF, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QImage, QPainter, QPainterPath

_MAX_BYTES = 5 * 1024 * 1024
_MAX_WIDTH = 640
# Matches Theme.radiusMd (10 px) when a 640 px image is shown at the 224 px
# hero width; smaller slots scale the corner down with the image.
_RADIUS_RATIO = 0.045
_TIMEOUT_SECONDS = 6
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def thumbnail_dir(cache_root: str | None = None) -> str:
    root = cache_root or QStandardPaths.writableLocation(
        QStandardPaths.CacheLocation
    )
    return os.path.join(root, "thumbs")


def _prepare(data: bytes) -> QImage | None:
    """Decode, crop to 16:9, downscale and round the corners of a thumbnail."""
    image = QImage.fromData(data)
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format_ARGB32)

    width, height = image.width(), image.height()
    if width * 9 != height * 16 and width and height:
        if width * 9 > height * 16:  # wider than 16:9: trim the sides
            crop_w = max(1, height * 16 // 9)
            image = image.copy((width - crop_w) // 2, 0, crop_w, height)
        else:  # taller than 16:9: trim top and bottom (letterboxed thumbs)
            crop_h = max(1, width * 9 // 16)
            image = image.copy(0, (height - crop_h) // 2, width, crop_h)
    if image.width() > _MAX_WIDTH:
        image = image.scaledToWidth(_MAX_WIDTH, Qt.SmoothTransformation)

    rounded = QImage(image.size(), QImage.Format_ARGB32)
    rounded.fill(Qt.transparent)
    radius = max(2.0, image.width() * _RADIUS_RATIO)
    path = QPainterPath()
    path.addRoundedRect(
        QRectF(0, 0, image.width(), image.height()), radius, radius
    )
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setClipPath(path)
    painter.drawImage(0, 0, image)
    painter.end()
    return rounded


def cached_thumbnail(video_id: str, cache_root: str | None = None) -> str:
    """The local URL of an already-cached thumbnail, or ``""``. No network."""
    safe_id = _SAFE_ID.sub("_", (video_id or "").strip())
    if not safe_id:
        return ""
    target = os.path.join(thumbnail_dir(cache_root), safe_id + ".png")
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        return QUrl.fromLocalFile(target).toString()
    return ""


def cache_thumbnail(
    video_id: str,
    remote_url: str,
    cache_root: str | None = None,
) -> str:
    """Return a local ``file:///`` URL for the thumbnail, or ``""``.

    ``cache_root`` overrides the Qt cache location (used by tests). A cache hit
    never touches the network.
    """
    safe_id = _SAFE_ID.sub("_", (video_id or "").strip())
    if not safe_id:
        return ""
    directory = thumbnail_dir(cache_root)
    target = os.path.join(directory, safe_id + ".png")

    cached = cached_thumbnail(video_id, cache_root)
    if cached:
        return cached

    if not remote_url:
        return ""

    try:
        os.makedirs(directory, exist_ok=True)
        with urllib.request.urlopen(remote_url, timeout=_TIMEOUT_SECONDS) as response:
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if int(length) > _MAX_BYTES:
                        return ""
                except ValueError:
                    pass
            data = response.read(_MAX_BYTES + 1)
        if not data or len(data) > _MAX_BYTES:
            return ""
        image = _prepare(data)
        if image is None:
            return ""
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".part")
        os.close(fd)
        try:
            if not image.save(temporary, "PNG"):
                raise OSError("PNG encode failed")
            os.replace(temporary, target)
        except OSError:
            try:
                os.remove(temporary)
            except OSError:
                pass
            return ""
        return QUrl.fromLocalFile(target).toString()
    except Exception:  # noqa: BLE001 - a thumbnail must never break inspection
        return ""
