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
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402,F401

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

from app.bridge import DEFAULT_ACCENT, DownloaderBridge, register_bundled_fonts  # noqa: E402
from app.queue import DONE, QUEUED, RUNNING, QueueJob  # noqa: E402

QML_DIR = ROOT / "ui" / "qml"


def _seed_history(bridge) -> None:
    """Three demo rows so the Library page has something to show."""
    demo = Path(tempfile.mkdtemp(prefix="saaaveit-demo-"))
    # The rows describe the video the shot is showing, so the job the bridge
    # would have filed them under is the one captured from the current form.
    job = bridge._capture_job(include_subtitle=True)
    rows = [
        ("Demo video [dQw4w9WgXcQ].mp4", "video", True),
        ("Demo video [dQw4w9WgXcQ].ja.srt", "subtitle", True),
        ("Deleted video [aaaaaaaaaaa].mp4", "video", False),
    ]
    for name, kind, exists in rows:
        path = demo / name
        if exists:
            path.write_bytes(b"x" * 3072)
        bridge._record(job, str(path), kind)


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


def _seed_log(bridge) -> None:
    """A few lines, including one of each severity, so the log has a shape.

    The status bar's counts come from ``_LOG_ERROR_RE``/``_LOG_WARN_RE``, which
    match a leading ``ERROR:``/``WARNING:`` — so the seed is written that way
    rather than by setting the counters.
    """
    bridge._append_log(
        "Inspecting https://example.com/video?v=dQw4w9WgXcQ\n"
        "WARNING: unable to download the thumbnail, using a placeholder\n"
        "ERROR: HTTP Error 403: Forbidden while fetching the video\n"
    )


def _seed_queue(bridge) -> list:
    """Three committed jobs, one per visible state, for the queue card.

    The states are written directly rather than downloaded: a shot has to show
    a saved row beside a live one without waiting on the network.
    """
    saved = QueueJob(id=1, url=bridge._url, title="First video",
                    format_label="1080p · mp4")
    saved.state = DONE
    saved.video_outcome = "ok"
    inflight = QueueJob(id=2, url=bridge._url, title="Second video",
                        format_label="720p · webm", subtitle_lang="ja",
                        subtitle_label="Japanese", subtitle_leg_wanted=True,
                        state=RUNNING, progress=40)
    waiting = QueueJob(id=3, url=bridge._url, title="Third video",
                       format_label="480p · mp4", state=QUEUED)
    bridge._queue = [saved, inflight, waiting]
    bridge._active = inflight
    bridge._download_running = True
    bridge.queueChanged.emit()
    bridge.downloadChanged.emit()
    return [saved, inflight, waiting]


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


def _shoot(root, outdir: Path, name: str) -> None:
    image = root.grabWindow()
    image.save(str(outdir / f"{name}.png"))
    print(f"{name}.png", image.width(), "x", image.height())


def main() -> int:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ROOT / "shots"
    outdir.mkdir(parents=True, exist_ok=True)

    app = QGuiApplication([])
    register_bundled_fonts()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))

    bridge = DownloaderBridge()
    bridge._url = "https://example.com/video?v=dQw4w9WgXcQ"
    bridge._info_gen += 1
    bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(_payload()))
    _seed_history(bridge)
    _seed_log(bridge)

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

    # ------------------------------------------------------- state shots
    # The redesign added surfaces the resting-state pages cannot show: a
    # selected library row (drawer), a failure banner, comfortable spacing,
    # and each accent. Seed, settle, grab, undo.

    # Drawer: the first row exists on disk, so Open/Redownload are live.
    bridge.selectHistory(0)
    root.setProperty("currentPage", 1)
    for theme in ("dark", "light"):
        bridge._theme_name = theme
        bridge.themeChanged.emit()
        _settle(app)
        _shoot(root, outdir, f"library-drawer-{theme}")
    bridge.selectHistory(-1)

    # Failure banner in the summary panel (dark only — the banner's own
    # colours carry it in both themes; the page set above covers light).
    bridge._theme_name = "dark"
    bridge.themeChanged.emit()
    root.setProperty("currentPage", 0)
    bridge._set_failure(
        "network",
        "The network gave up",
        "ERROR: HTTP Error 503: Service Unavailable while fetching the video",
        "Check your connection (or proxy) and retry. A part-fetched file "
        "resumes where it stopped.",
    )
    _settle(app)
    _shoot(root, outdir, "failure-banner-dark")
    bridge.dismissFailure()

    # A committed batch: one row saved, one in flight, one still waiting. The
    # card is at the foot of the flow, so the shot scrolls down to it the way a
    # user would after queueing a second video. ``ScrollView`` is the frame, not
    # the scroller: the content offset belongs to the flickable inside it.
    _seed_queue(bridge)
    _settle(app)          # the card's height is only real after a layout pass
    scroller = root.findChild(QQuickItem, "download.flowScroller")
    lane = next((child for child in scroller.children()
                 if child.metaObject().className().startswith("QQuickFlickable")), None)
    if lane is not None:
        lane.setProperty("contentY", max(
            0, lane.property("contentHeight") - lane.property("height")))
    _settle(app)
    _shoot(root, outdir, "queue-batch-dark")
    bridge._queue = []
    bridge._active = None
    bridge._download_running = False
    bridge.queueChanged.emit()
    bridge.downloadChanged.emit()

    # Comfortable spacing on the densest page.
    bridge.setComfortable(True)
    root.setProperty("currentPage", 2)
    _settle(app)
    _shoot(root, outdir, "settings-comfortable-dark")
    bridge.setComfortable(False)

    # Every accent, on the Download page where the accent does the most work.
    root.setProperty("currentPage", 0)
    bridge._theme_name = "dark"
    bridge.themeChanged.emit()
    for choice in bridge.accentChoices:
        bridge.setAccent(choice["id"])
        _settle(app)
        _shoot(root, outdir, f"accent-{choice['id']}-dark")
    bridge.setAccent(DEFAULT_ACCENT)

    # Shortcut recording mid-capture: the armed row and the live error line.
    root.setProperty("currentPage", 2)
    bridge.setShortcut("inspect", "")  # an unassigned row reads differently
    root.setProperty("capturingAction", bridge.shortcutRows[0]["action"])
    root.setProperty("capturingShortcuts", True)
    root.setProperty("captureMessage", "Shortcuts need Ctrl or Alt.")
    _settle(app)
    _shoot(root, outdir, "shortcuts-recording-dark")
    root.setProperty("capturingShortcuts", False)
    root.setProperty("capturingAction", "")
    root.setProperty("captureMessage", "")
    bridge.resetAllShortcuts()

    # The two overlays, on top of the Download page. They are the only surfaces
    # a page shot cannot show, and both are scrollable.
    root.setProperty("currentPage", 0)
    bridge._theme_name = "dark"
    bridge.themeChanged.emit()
    _settle(app)
    for object_name, shot in (("commandPalette", "overlay-palette-dark"),
                              ("logDialog", "overlay-log-dark")):
        overlay = root.findChild(QQuickItem, object_name)
        if overlay is None:
            print("missing overlay:", object_name)
            continue
        overlay.setProperty("visible", True)
        _settle(app)
        _shoot(root, outdir, shot)
        overlay.setProperty("visible", False)
        _settle(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
