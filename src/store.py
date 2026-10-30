"""Persisted settings and download history for the downloader.

The app owns its own ``QSettings`` organisation/application pair so it can never
collide with another application's stored keys on the same machine.
"""
from __future__ import annotations

import json
import os
import sys
import time

from PySide6.QtCore import QSettings

ORGANISATION = "Njoro"
APPLICATION = "Saaaveit"

DEFAULT_FILENAME_TEMPLATE = "%(title)s [%(id)s]"


def settings() -> QSettings:
    """The one settings store this app reads and writes."""
    return QSettings(ORGANISATION, APPLICATION)


def app_data_dir() -> str:
    """Per-user folder for state that does not belong next to the executable."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":  # pragma: no cover - platform specific
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:  # pragma: no cover - platform specific
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(root, APPLICATION)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = os.path.expanduser("~")
    return path


def load_history(store: QSettings) -> list[dict]:
    """Decode the persisted download history (newest first)."""
    raw = store.value("downloads/history", "[]")
    try:
        entries = json.loads(raw if isinstance(raw, str) else "[]")
    except (TypeError, ValueError):
        return []
    return [e for e in entries if isinstance(e, dict) and e.get("path")]


def save_history(store: QSettings, entries: list[dict]) -> None:
    store.setValue("downloads/history", json.dumps(entries[:200]))
    store.sync()


def make_entry(
    *,
    path: str,
    kind: str,
    title: str,
    video_id: str,
    url: str,
    detail: str,
    size: int,
) -> dict:
    """A history row for one downloaded file."""
    return {
        "path": path,
        "kind": kind,            # "video" | "subtitle"
        "title": title or os.path.basename(path),
        "videoId": video_id,
        "url": url,
        "detail": detail,
        "size": int(size or 0),
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "timestamp": time.time(),
    }
