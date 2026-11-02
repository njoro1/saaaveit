"""Offscreen keyboard audit: which controls can a Tab-only user reach?

    python tools/keyboard_audit.py

Sends real ``Tab`` key events to the running window and reports the object name
of the item that ends up with active focus, once per page. Controls built from a
plain ``Item`` or ``Rectangle`` with only a ``MouseArea`` never appear here, and
that is the point: a control that cannot be tabbed to cannot be used with the
keyboard, however complete its ``Accessible`` properties look.

The download page is seeded with a synthetic inspection payload so the format,
subtitle and action controls exist, and the library gets one fake history row.
Nothing here touches the network.

Items are found by walking ``QQuickItem::childItems()``, not ``findChildren()``:
``ListView`` delegates are not reachable through the QObject child list, so a
``findChildren``-based audit silently misses every row control.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QT_QPA_FONTDIR",
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
)
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QSettings, QObject, Qt, QUrl, QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

_scratch = tempfile.mkdtemp(prefix="saaaveit-keyboard-")
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _scratch)
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, _scratch)

from app.bridge import DownloaderBridge, register_bundled_fonts  # noqa: E402
from src import media_source, store  # noqa: E402

PAGES = {0: "Download", 1: "Library", 2: "Settings"}


def _seed_payload() -> dict:
    codecs, resolutions, matrix, best = media_source._build_matrix([
        {"format_id": "401", "ext": "mp4", "height": 1080,
         "vcodec": "av01.0.13M.10", "acodec": "none", "tbr": 5000,
         "filesize": 40_000_000, "fps": 30},
        {"format_id": "248", "ext": "webm", "height": 1080,
         "vcodec": "vp9", "acodec": "none", "tbr": 4000,
         "filesize": 45_000_000, "fps": 30},
    ])[:4]
    return {
        "title": "Audit video",
        "video_id": "audit0001",
        "uploader": "Audit channel",
        "duration": 613,
        "language": "ja",
        "codecs": codecs,
        "resolutions": resolutions,
        "matrix": matrix,
        "best": best,
        "codecs_available": {"av1": True, "vp9": True, "h264": False},
        "subtitle_tracks": [
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": False},
        ],
        "default_subtitle_track": "ja",
    }


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication([])
    register_bundled_fonts()
    bridge = DownloaderBridge()
    engine = QQmlApplicationEngine()
    engine.addImportPath(os.path.join(ROOT, "ui", "qml"))
    engine.rootContext().setContextProperty("appBridge", bridge)
    engine.load(QUrl.fromLocalFile(os.path.join(ROOT, "ui", "qml", "Main.qml")))
    if not engine.rootObjects():
        print("Main.qml did not load", file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]
    window.resize(1240, 820)
    window.setVisible(True)

    def settle(ms: int = 300) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        for _ in range(4):
            app.processEvents()

    settle()

    bridge._url = "https://example.invalid/watch?v=audit0001"
    bridge._notify_form_changed()
    bridge._info_gen += 1
    bridge._on_info_done(
        f"INFO:{bridge._info_gen}|" + json.dumps(_seed_payload())
    )
    # One library row, so the row's action buttons exist for the walk.
    saved = os.path.join(_scratch, "Audit video [audit0001].mp4")
    with open(saved, "wb") as handle:
        handle.write(b"not a real video")
    bridge._record(saved, "video")
    settle(600)

    anchor = window.findChild(QQuickItem, "libraryPage")
    if anchor is None:
        print("libraryPage not found", file=sys.stderr)
        return 1
    root_item: QQuickItem = anchor
    while isinstance(root_item.parent(), QQuickItem):
        root_item = root_item.parent()

    def visual_tree() -> list[tuple[QQuickItem, int]]:
        out: list[tuple[QQuickItem, int]] = []

        def walk(node: QQuickItem, depth: int) -> None:
            out.append((node, depth))
            for child in node.childItems():
                walk(child, depth + 1)

        walk(root_item, 0)
        return out

    def label(item: QObject) -> str:
        cls = item.metaObject().className().split("_QMLTYPE")[0]
        hint = item.property("iconName") or item.property("text") or ""
        name = item.objectName() or "?"
        return f"{name} [{cls}] {hint}".rstrip()

    def focused() -> QQuickItem | None:
        hits = [
            (item, depth) for item, depth in visual_tree()
            if item.property("activeFocus") is True
        ]
        if not hits:
            return None
        hits.sort(key=lambda pair: pair[1])
        return hits[-1][0]

    total: set[str] = set()
    for index, title in PAGES.items():
        window.setProperty("currentPage", index)
        settle()
        stops: list[str] = []
        # 90 presses: the redesigned pages run longer than the old ones (the
        # format matrix alone adds a dozen cells, the shortcut rows two buttons
        # each), and a chain that never wraps proves nothing about reachability.
        for _ in range(90):
            QTest.keyClick(window, Qt.Key_Tab)
            app.processEvents()
            item = focused()
            stops.append(label(item) if item else "<none>")
        reachable = [name for name in dict.fromkeys(stops) if name != "<none>"]
        total.update(reachable)
        print(f"--- {title}: {len(reachable)} tab stops")
        for name in reachable:
            print(f"    {name}")
        wrapped = stops[-1] in stops[:-1]
        print(f"    (chain wrapped after {len(stops)} presses: {wrapped})")
    print(f"--- reachable with the keyboard anywhere: {len(total)} controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
