"""Render the app offscreen and save one PNG per theme.

Used to verify visual changes without a desktop session. Run from the project
root:  python tools/screenshot.py [outdir]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
# The offscreen platform uses a basic font database; without this it renders
# every glyph as a box. Point it at the system font directory.
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
# Importing QtQuick registers QQuickWindow with the binding layer; without it
# ``rootObjects()[0]`` degrades to a plain QWindow and ``grabWindow()`` is gone.
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401

# Isolate persisted state before the bridge is imported/constructed: a
# screenshot must never read or write the user's real settings and history.
# ``QSettings.setDefaultFormat`` is not enough here — Qt has already created
# QSettings instances by the time the GUI modules are imported on Windows, so
# the store is replaced outright.
from PySide6.QtCore import QSettings  # noqa: E402
from src import media_source, store  # noqa: E402

_SHOTS_SETTINGS = QSettings(
    str(Path(tempfile.mkdtemp(prefix="saaaveit-shots-")) / "settings.ini"),
    QSettings.IniFormat,
)
_SHOTS_SETTINGS.clear()
_SHOTS_SETTINGS.sync()
store.settings = lambda: _SHOTS_SETTINGS

from app.bridge import DownloaderBridge  # noqa: E402

QML_DIR = ROOT / "ui" / "qml"


def _seed_history(bridge) -> None:
    """Three demo rows so the Library page has something to show."""
    demo = Path(tempfile.mkdtemp(prefix="saaaveit-demo-"))
    rows = [
        ("Demo video [dQw4w9WgXcQ].mp4", "video", True),
        ("Demo video [dQw4w9WgXcQ].ja.srt", "subtitle", True),
        ("Deleted video [aaaaaaaaaaa].mp4", "video", False),
    ]
    for name, kind, exists in rows:
        path = demo / name
        if exists:
            path.write_bytes(b"x" * 3072)
        bridge._record(str(path), kind)


def _payload() -> dict:
    codecs, resolutions, matrix, best = media_source._build_matrix([
        {"format_id": "401", "ext": "mp4", "height": 1080,
         "vcodec": "av01.0.13M.10", "acodec": "none", "tbr": 5000,
         "filesize": 40_000_000, "fps": 30},
        {"format_id": "137", "ext": "mp4", "height": 1080,
         "vcodec": "avc1.640028", "acodec": "none", "tbr": 4500,
         "filesize": 36_000_000, "fps": 30},
        {"format_id": "140", "ext": "m4a", "height": None,
         "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128,
         "filesize": 4_000_000},
    ])[:4]
    return {
        "title": "How the app renders offline",
        "video_id": "dQw4w9WgXcQ",
        "language": "ja",
        "codecs": codecs,
        "resolutions": resolutions,
        "matrix": matrix,
        "best": best,
        "codecs_available": {"av1": True, "vp9": False, "h264": True},
        "subtitle_tracks": [
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": False},
        ],
        "default_subtitle_track": "ja",
    }


def _settle(app, ms: int = 260) -> None:
    """Pump events for real time so theme ``ColorAnimation``s finish.

    ``processEvents`` alone does not advance animation timers, so a grab right
    after a theme switch catches controls mid-fade (e.g. a dark button fill on
    a light page).
    """
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "shots"
    outdir.mkdir(parents=True, exist_ok=True)

    app = QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))

    bridge = DownloaderBridge()
    bridge._url = "https://example.com/video?v=dQw4w9WgXcQ"
    bridge._info_gen += 1
    bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(_payload()))
    _seed_history(bridge)

    engine.rootContext().setContextProperty("appBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    root = engine.rootObjects()[0]
    root.show()

    for page in (0, 1, 2):
        root.setProperty("currentPage", page)
        for theme in ("dark", "light"):
            bridge._theme_name = theme
            bridge.themeChanged.emit()
            _settle(app)
            image = root.grabWindow()
            name = f"page{page}-{theme}.png"
            image.save(str(outdir / name))
            print(name, image.width(), "x", image.height())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
