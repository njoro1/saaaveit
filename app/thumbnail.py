"""Download and cache video thumbnails on a worker thread.

The frozen build does not ship QtNetwork or TLS QML plugins, so QML must never
load a remote image. This module turns the thumbnail URL from inspection into a
local ``file:///`` URL under the app's cache directory. Failures are silent by
design: a missing thumbnail is decorative, never an error the user must see.
"""
from __future__ import annotations

import os
import re
import tempfile
import urllib.request

from PySide6.QtCore import QStandardPaths, QUrl

_MAX_BYTES = 5 * 1024 * 1024
_TIMEOUT_SECONDS = 6
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def thumbnail_dir(cache_root: str | None = None) -> str:
    root = cache_root or QStandardPaths.writableLocation(
        QStandardPaths.CacheLocation
    )
    return os.path.join(root, "thumbs")


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
    target = os.path.join(directory, safe_id + ".jpg")

    if os.path.isfile(target) and os.path.getsize(target) > 0:
        return QUrl.fromLocalFile(target).toString()

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
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
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
