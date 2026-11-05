"""The downloader's QML must load cleanly and expose the whole flow.

These tests drive the real ``Main.qml`` (offscreen) against the real
``DownloaderBridge``. They are structural: the point is that the three pages
exist, the subtitle picker is part of the download, and nothing that belongs to
another application appears anywhere in the UI.
"""
from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QMetaObject, QObject, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from src import media_source
from app.queue import DONE, FAILED, RUNNING, QueueJob

QML_DIR = Path(__file__).resolve().parent.parent / "ui" / "qml"


def _info_payload() -> dict:
    codecs, resolutions, matrix, best = media_source._build_matrix([
        {"format_id": "401", "ext": "mp4", "height": 1080,
         "vcodec": "av01.0.13M.10", "acodec": "none", "tbr": 5000,
         "filesize": 40_000_000, "fps": 30},
        {"format_id": "140", "ext": "m4a", "height": None,
         "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128,
         "filesize": 4_000_000},
    ])[:4]
    return {
        "title": "A test video",
        "video_id": "dQw4w9WgXcQ",
        "language": "ja",
        "codecs": codecs,
        "resolutions": resolutions,
        "matrix": matrix,
        "best": best,
        "codecs_available": {"av1": True, "vp9": False, "h264": False},
        "subtitle_tracks": [
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
            {"code": "ja", "name": "Japanese (auto)", "kind": "auto",
             "label": "Japanese (auto) · auto", "isOriginal": True},
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": False},
        ],
        "default_subtitle_track": "ja",
    }


@pytest.fixture(scope="module")
def ui(qml_main):
    bridge = qml_main.bridge
    # Bypass the ``url`` setter: it auto-inspects over the network. The payload
    # below is synthetic, so no live request should ever start.
    bridge._url = "https://example.com/video?v=dQw4w9WgXcQ"
    bridge._notify_form_changed()
    # Downloads in other modules save the format preference on their first
    # job; the shared session bridge must hand every module a clean slate.
    bridge.preferredCodec = ""
    bridge.preferredResolution = ""
    bridge._info_gen += 1
    bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(_info_payload()))
    qml_main.warnings.clear()
    return qml_main


def _find(root: QObject, name: str) -> QObject:
    obj = root.findChild(QObject, name)
    assert obj is not None, f"{name} not found (objectName missing?)"
    return obj


def _find_item(root: QObject, name: str) -> QQuickItem:
    """Like ``_find``, but as a visual item so children can be walked.

    ``findChildren(QObject)`` does not reach ``ListView`` delegates or any child
    created inside a QML component body, which is why the row-level assertions
    below traverse ``childItems()`` instead.
    """
    obj = root.findChild(QQuickItem, name)
    assert obj is not None, f"{name} not found as a QQuickItem"
    return obj


def _place(item: QQuickItem, ancestor: QQuickItem) -> tuple:
    """``item``'s box in ``ancestor``'s coordinates, as ``(x, y, w, h)``."""
    point = item.mapToItem(ancestor, 0, 0)
    return (point.x(), point.y(), float(item.property("width")),
            float(item.property("height")))


def _visual_tree(item: QQuickItem) -> list:
    out = []

    def walk(node) -> None:
        for child in node.childItems():
            out.append(child)
            walk(child)

    walk(item)
    return out


def _show_page(root: QObject, index: int, app) -> None:
    """Make a StackLayout page current so its delegates exist.

    A hidden ``ListView`` lays out nothing, so ``childItems()`` stays empty and
    row-level assertions would pass against a subtree that was never built.
    Delegates appear on a later pass than the visibility change, hence the wait.
    """
    root.setProperty("currentPage", index)
    app.processEvents()
    QTest.qWait(60)
    app.processEvents()


def _library_row(root: QObject, app, needle: str) -> list:
    """The rendered row containing ``needle``, as its own subtree.

    History outlives a single test, so assertions are scoped to one delegate
    rather than the whole table. Note that every label of a delegate exists
    whatever the state - ``missing from disk`` is a static string behind a
    ``visible:`` binding - so callers must look at visibility, not presence.
    """
    table = _find_item(root, "library.table")
    _show_page(root, 1, app)
    match = [item for item in _visual_tree(table)
             if needle in str(item.property("text") or "")]
    assert match, f"no rendered row mentions {needle!r}"
    node = match[0]
    while node.parentItem() is not None and node.parentItem().parentItem() is not table:
        node = node.parentItem()
    return _visual_tree(node)


def _shown_text(items: list) -> list:
    return [str(item.property("text")) for item in items
            if item.property("text") is not None and bool(item.property("visible"))]


def _focused_item(surface: QQuickItem):
    """The deepest item holding active focus, or ``None``.

    ``activeFocus`` is true for every ancestor of the focused item too, so the
    control the user actually sees is the deepest match.
    """
    found: list[tuple[int, QQuickItem]] = []

    def walk(node, level: int) -> None:
        if node.property("activeFocus") is True:
            found.append((level, node))
        for child in node.childItems():
            walk(child, level + 1)

    walk(surface, 0)
    return max(found)[1] if found else None


def _focus_by_tabbing(ui, name: str, presses: int = 60) -> bool:
    """Tab until ``name`` holds focus. True if it got there."""
    app = QGuiApplication.instance()
    surface = ui.root.contentItem()
    for _ in range(presses):
        QTest.keyClick(ui.root, Qt.Key_Tab)
        app.processEvents()
        focused = _focused_item(surface)
        if focused is not None and focused.objectName() == name:
            return True
    return False


def _leave_library(ui, app) -> None:
    """Back to Download, so later tests still see the page they expect."""
    ui.root.setProperty("currentPage", 0)
    app.processEvents()


@contextlib.contextmanager
def _one_history_row(ui, path):
    """A library holding exactly ``path``.

    History is shared by the whole module, and a delegate from an older row is
    recycled into the new one - so a stale ``missing from disk`` label can show
    up in the subtree of a file that exists. One row makes that impossible.
    """
    bridge = ui.bridge
    saved = list(bridge._history)
    bridge._history = []
    bridge._record(
        QueueJob(
            id=1,
            url=bridge._url,
            title=bridge._title,
            video_id=bridge._video_id,
            format_label=bridge.selectedFormatLabel,
        ),
        str(path),
        "video",
    )
    try:
        yield
    finally:
        bridge._history = saved
        bridge.historyChanged.emit()


@contextlib.contextmanager
def _log_lines(ui, text: str):
    """Log content, restored afterwards.

    ``_append_log`` counts severities per chunk, so the counters have to be put
    back by hand as well as the text.
    """
    bridge = ui.bridge
    saved = (bridge._log_text, bridge._log_error_count, bridge._log_warn_count)
    bridge._append_log(text)
    # ``logTextChanged`` is throttled to a beat rather than fired per line, so
    # let that beat run before the dialog is asked to show the log.
    QTest.qWait(300)
    QGuiApplication.instance().processEvents()
    try:
        yield
    finally:
        (bridge._log_text, bridge._log_error_count,
         bridge._log_warn_count) = saved
        bridge.logTextChanged.emit()
        bridge.logCountsChanged.emit()


def _press(obj: QObject) -> None:
    """Click a QML button for real: ``click()`` runs its whole press logic."""
    _call(obj, "click")


def _click_at(window: QObject, x: float, y: float) -> None:
    """A press and release at a window-local point.

    ``QQuickMouseArea.clicked`` carries a ``QQuickMouseEvent``, so it cannot be
    emitted from Python; anything that has to test a mouse-only affordance - a
    scrim, a row, a swatch - has to be clicked with real events.
    """
    from PySide6.QtGui import QMouseEvent

    position = QPointF(x, y)
    buttons = Qt.MouseButton.LeftButton
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QGuiApplication.sendEvent(
            window,
            QMouseEvent(kind, position, position, buttons, buttons,
                        Qt.KeyboardModifier.NoModifier),
        )
    QGuiApplication.instance().processEvents()


def _app_shortcuts(root: QObject) -> dict:
    """The window's live chords, as ``sequence -> enabled``.

    ``Shortcut`` is a non-visual item, so the metaobject is the only way to see
    what the app will actually answer to. The modals' own ``Escape`` handlers
    share the class; callers key off the bridge's map and never look at those.
    """
    out: dict[str, bool] = {}
    for child in root.findChildren(QObject):
        if child.metaObject().className().startswith("QQuickShortcut"):
            out[str(child.property("sequence") or "")] = bool(child.property("enabled"))
    return out


def _call(obj: QObject, method: str) -> None:
    """Invoke a zero-argument QML-declared function."""
    meta = obj.metaObject()
    index = meta.indexOfMethod(method + "()")
    assert index >= 0, f"{method}() is not invokable on {obj.objectName()}"
    assert QMetaObject.invokeMethod(obj, method)


def _stack(root: QObject) -> QObject:
    for child in root.findChildren(QObject):
        if child.metaObject().className().startswith("QQuickStackLayout"):
            return child
    raise AssertionError("no StackLayout found in Main.qml")


class TestShell:
    def test_main_qml_loads_without_warnings(self, ui):
        assert ui.root is not None
        assert ui.warnings == [], ui.warnings

    def test_theme_fonts_resolve_to_installed_families(self, ui):
        """``Theme.uiFont``/``monoFont`` must name a family Qt can actually load."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtQml import QQmlComponent

        component = QQmlComponent(ui.engine)
        component.setData(
            b"import QtQuick\nimport \".\"\n"
            b"QtObject {\n"
            b"  property string ui: Theme.uiFont\n"
            b"  property string mono: Theme.monoFont\n"
            b"}\n",
            QUrl.fromLocalFile(str(QML_DIR / "ThemeProbe.qml")),
        )
        assert component.isReady(), [e.toString() for e in component.errors()]
        probe = component.create()
        assert probe is not None, [e.toString() for e in component.errors()]
        families = set(QFontDatabase.families())
        assert probe.property("ui") in families
        assert probe.property("mono") in families

    def test_style_pin_overrides_the_environment(self, monkeypatch):
        import main

        monkeypatch.setenv("QT_QUICK_CONTROLS_STYLE", "Fusion")
        main._pin_style()
        import os

        assert os.environ["QT_QUICK_CONTROLS_STYLE"] == "Basic"

    def test_all_three_pages_exist(self, ui):
        names = ["downloadPage", "libraryPage", "settingsPage"]
        for name in names:
            obj = ui.root.findChild(QObject, name)
            assert obj is not None, f"{name} is missing from Main.qml"

    def test_navigation_switches_the_stack(self, ui):
        stack = _stack(ui.root)
        ui.root.setProperty("currentPage", 2)
        assert stack.property("currentIndex") == 2
        ui.root.setProperty("currentPage", 0)
        assert stack.property("currentIndex") == 0

    def test_pages_stay_alive_when_switched(self, ui):
        page = _find(ui.root, "libraryPage")
        ui.root.setProperty("currentPage", 2)
        ui.root.setProperty("currentPage", 1)
        assert _find(ui.root, "libraryPage") is page


class TestDownloadPage:
    def test_url_and_actions_are_present(self, ui):
        for name in ("download.urlField", "download.inspectButton",
                     "download.downloadButton", "download.cancelButton",
                     "download.subtitleOnlyButton", "download.folderLabel"):
            assert _find(ui.root, name) is not None

    def test_hero_carries_the_media_identity(self, ui):
        thumb = _find(ui.root, "download.mediaThumb")
        assert thumb.property("source").toString() == ""
        assert thumb.property("duration") == 0
        assert _find(ui.root, "download.heroTitle").property("text") == "A test video"
        assert _find(ui.root, "download.heroChannel").property("text") == ""

    def test_inspect_button_tracks_the_url(self, ui):
        button = _find(ui.root, "download.inspectButton")
        bridge = ui.bridge
        saved = bridge.url
        try:
            bridge._url = ""
            bridge._notify_form_changed()
            assert button.property("enabled") is False
            bridge._url = saved
            bridge._notify_form_changed()
            assert button.property("enabled") is True
        finally:
            bridge._url = saved
            bridge._notify_form_changed()

    def test_stage_and_progress_are_rendered(self, ui):
        stage = _find(ui.root, "download.stageLabel")
        assert stage.property("text") != ""
        assert ui.bridge.downloadProgress == 0

    def test_format_matrix_shows_the_offered_pairs(self, ui):
        matrix = _find(ui.root, "download.formatMatrix")
        assert matrix is not None
        assert _find(ui.root, "download.bestCell") is not None
        assert len(ui.bridge.formatRows) >= 1

    def test_download_button_is_enabled_with_a_selection(self, ui):
        button = _find(ui.root, "download.downloadButton")
        assert ui.bridge.canDownload is True
        assert button.property("enabled") is True

    def test_paste_reads_as_a_button_beside_clear(self, ui):
        """An affordance, not a word: the same treatment as its neighbour."""
        paste = _find(ui.root, "download.pasteButton")
        clear = _find(ui.root, "download.clearButton")
        assert str(paste.property("variant")) == str(clear.property("variant"))
        assert float(paste.property("implicitHeight")) == \
            float(clear.property("implicitHeight"))

    def test_paste_button_pushes_the_clipboard_into_the_url(self, ui, monkeypatch):
        button = _find(ui.root, "download.pasteButton")
        assert button is not None
        bridge = ui.bridge
        # The setter inspects; the harness feeds payloads, not the network.
        monkeypatch.setattr(bridge, "inspect", lambda: None)
        saved_url = bridge._url
        clip = QGuiApplication.clipboard()
        saved_clip = clip.text()
        try:
            bridge._url = ""
            clip.setText("https://example.com/pasted?v=abcd\nsecond line")
            _press(button)
            assert bridge.url == "https://example.com/pasted?v=abcd"
        finally:
            clip.setText(saved_clip or "")
            bridge._url = saved_url
            # The paste went through the real setter, so the inspection state
            # of the module-shared bridge is gone. Re-install the fixture's
            # payload the way the fixture itself does.
            bridge._info_gen += 1
            bridge._on_info_done(
                f"INFO:{bridge._info_gen}|" + json.dumps(_info_payload()))
            bridge._notify_form_changed()

    def test_the_form_stays_live_while_a_job_downloads(self, ui):
        """Queuing the next video is only useful if the form can be used at all."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        saved = (bridge._download_running, bridge._active, list(bridge._queue))
        bridge._queue = [QueueJob(id=99, url=bridge._url, title="Running job")]
        bridge._active = bridge._queue[0]
        bridge._download_running = True
        try:
            bridge.downloadChanged.emit()
            bridge.queueChanged.emit()
            _show_page(ui.root, 0, app)

            for name in ("download.urlField", "download.clearButton",
                         "download.inspectButton", "download.formatMatrix",
                         "download.bestCell", "download.subtitleTracks",
                         "download.downloadButton"):
                assert _find(ui.root, name).property("enabled") is True, name

            button = _find(ui.root, "download.downloadButton")
            assert button.property("text") == "Add to queue"
            assert _find(ui.root, "download.cancelButton").property("visible") is True
            assert _find(ui.root, "download.whyNot").property("visible") is False
        finally:
            (bridge._download_running, bridge._active, bridge._queue) = saved
            bridge.downloadChanged.emit()
            bridge.queueChanged.emit()
            app.processEvents()

    def test_a_waiting_queue_offers_to_start_it(self, ui):
        """Work restored from the last session: nothing runs, so start it."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        saved = list(bridge._queue)
        bridge._queue = [QueueJob(id=1, url=bridge._url, title="Waiting job")]
        try:
            bridge.queueChanged.emit()
            _show_page(ui.root, 0, app)
            button = _find(ui.root, "download.downloadButton")
            assert button.property("text") == "Start queue"
            assert button.property("enabled") is True
        finally:
            bridge._queue = saved
            bridge.queueChanged.emit()
            app.processEvents()

    def test_a_finished_download_retires_the_button(self, ui):
        """The video on screen is saved at the format on screen: say so."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        saved_last = bridge._last
        job = bridge._capture_job(include_subtitle=False)
        job.state = DONE
        job.video_outcome = "ok"
        try:
            bridge._last = job
            bridge.queueChanged.emit()
            _show_page(ui.root, 0, app)

            button = _find(ui.root, "download.downloadButton")
            assert button.property("text") == "Completed"
            assert button.property("enabled") is False
            assert _find(ui.root, "download.whyNot").property("text") == (
                "Already downloaded — pick another format to fetch it again.")

            # A different cell is a different download, so the button means it.
            bridge.pickFormat("av1", 1080)
            bridge.queueChanged.emit()
            app.processEvents()
            assert button.property("text") == "Download"
            assert button.property("enabled") is True
        finally:
            bridge._last = saved_last
            bridge.pickFormat("best", "best")
            bridge.queueChanged.emit()
            app.processEvents()

    def test_a_long_blocked_reason_elides_instead_of_overflowing_the_bar(self, ui):
        """Review F8: a non-filling Layout item is sized to its preferred width.

        Which is the whole implicit width, ellipsis or no ellipsis - so a long
        reason ran off the right edge of the action bar instead of eliding. The
        reason is derived from the readiness list and cannot be injected through
        the bridge, so the label's own text is set: that is what the layout sees.
        """
        app = QGuiApplication.instance()
        label = _find_item(ui.root, "download.blockedReason")
        row = label.parentItem()
        saved = (ui.root.property("width"), ui.root.property("height"),
                 label.property("text"), label.property("visible"))
        try:
            label.setProperty("text", "Pick " + " ".join(["a long reason"] * 20))
            label.setProperty("visible", True)
            ui.root.resize(560, 700)
            app.processEvents()

            implicit = float(label.property("implicitWidth"))
            width = float(label.property("width"))
            right = float(label.property("x")) + width
            assert width < implicit, f"label kept its implicit width: {width} of {implicit}"
            assert right <= float(row.property("width")) + 1.0, (
                f"the row is {row.property('width')} wide, the reason ends at {right}")
        finally:
            ui.root.resize(saved[0], saved[1])
            label.setProperty("text", saved[2])
            label.setProperty("visible", saved[3])
            app.processEvents()

    def test_a_long_headline_stays_inside_the_bar(self, ui):
        """Review F8 again, at the other capped label in the shell."""
        app = QGuiApplication.instance()
        label = _find_item(ui.root, "chrome.headline")
        row = label.parentItem()
        saved = (ui.root.property("width"), ui.root.property("height"),
                 label.property("visible"), label.property("text"))
        try:
            label.setProperty("visible", True)
            label.setProperty("text", " ".join(["a long inspecting title"] * 25))
            ui.root.resize(560, 700)
            app.processEvents()

            width = float(label.property("width"))
            assert width <= float(label.property("implicitWidth"))
            assert float(label.property("x")) + width <= float(row.property("width")) + 1.0, (
                f"the bar is {row.property('width')} wide and the headline ends at "
                f"{float(label.property('x')) + width}")
        finally:
            ui.root.resize(saved[0], saved[1])
            label.setProperty("visible", saved[2])
            label.setProperty("text", saved[3])
            app.processEvents()

    def test_download_button_is_disabled_without_a_selection(self, ui):
        bridge = ui.bridge
        saved = bridge.selectedResolution
        try:
            bridge.selectedCodec = "h264"
            bridge.selectedResolution = "2160"  # not offered
            button = _find(ui.root, "download.downloadButton")
            assert bridge.canDownload is False
            assert button.property("enabled") is False
        finally:
            bridge.selectedCodec = bridge.codecs[0]["id"]
            bridge.selectedResolution = saved


@contextlib.contextmanager
def _batch(bridge):
    """Seed three committed jobs: one saved, one in flight, one still waiting.

    The ``ui`` bridge is shared by the whole module, so the queue is handed back
    as it was found. Nothing here runs a real download: the states are written
    directly, which is exactly what the card reads.
    """
    app = QGuiApplication.instance()
    saved = (bridge._download_running, bridge._active, list(bridge._queue))
    finished = QueueJob(id=1, url=bridge._url, title="First video",
                        format_label="1080p · mp4")
    finished.state = DONE
    finished.video_outcome = "ok"
    inflight = QueueJob(id=2, url=bridge._url, title="Second video",
                        format_label="720p · webm", subtitle_lang="ja",
                        subtitle_label="Japanese", subtitle_leg_wanted=True)
    inflight.state = RUNNING
    waiting = QueueJob(id=3, url=bridge._url, title="Third video",
                       format_label="480p · mp4")
    bridge._queue = [finished, inflight, waiting]
    bridge._active = inflight
    bridge._download_running = True
    bridge.queueChanged.emit()
    bridge.downloadChanged.emit()
    app.processEvents()
    try:
        yield bridge._queue
    finally:
        (bridge._download_running, bridge._active, bridge._queue) = saved
        # Both notifies: the card reads the queue, the button and the banner
        # read the lane, and a binding left stale here outlives the test.
        bridge.queueChanged.emit()
        bridge.downloadChanged.emit()
        app.processEvents()


def _queue_rows(root: QObject, app) -> list:
    """The rendered queue rows, in list order, as ``objectName -> item``.

    ``findChild`` reaches only the first match and delegates are not its
    children, so each row is taken from the view's own visual subtree.
    """
    view = _find_item(root, "queue.list")
    rows = [item for item in _visual_tree(view)
            if item.property("objectName") == "queue.row"]
    rows.sort(key=lambda item: item.y())
    out = []
    for row in rows:
        cells = {}
        for item in _visual_tree(row):
            name = str(item.property("objectName") or "")
            if name:
                cells.setdefault(name, item)
        out.append(cells)
    return out


class TestQueueList:
    """The card that lets a batch be watched and pruned one job at a time."""

    def test_no_card_without_a_queue(self, ui):
        """An empty queue must not hold a slot in the flow."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        saved = list(bridge._queue)
        bridge._queue = []
        try:
            bridge.queueChanged.emit()
            _show_page(ui.root, 0, app)
            assert _find(ui.root, "queue.card").property("visible") is False
        finally:
            bridge._queue = saved
            bridge.queueChanged.emit()
            app.processEvents()

    def test_one_row_per_job_in_queue_order(self, ui):
        app = QGuiApplication.instance()
        with _batch(ui.bridge):
            _show_page(ui.root, 0, app)
            assert _find(ui.root, "queue.card").property("visible") is True
            rows = _queue_rows(ui.root, app)
            assert len(rows) == 3, [row["queue.rowTitle"].property("text")
                                    for row in rows]
            assert [row["queue.rowTitle"].property("text") for row in rows] == [
                "1.  First video", "2.  Second video", "3.  Third video"]
            assert _find(ui.root, "queue.count").property("text") == "1 waiting"

    def test_each_row_states_its_own_state_and_picks(self, ui):
        """A row is the only place a waiting job says what it will fetch."""
        app = QGuiApplication.instance()
        with _batch(ui.bridge):
            _show_page(ui.root, 0, app)
            rows = _queue_rows(ui.root, app)
            assert [row["queue.rowDetail"].property("text") for row in rows] == [
                "Saved · 1080p · mp4",
                "Downloading 2 of 3 · 720p · webm · Japanese",
                "Waiting · 480p · mp4"]

    def test_only_the_in_flight_row_can_be_cancelled(self, ui):
        app = QGuiApplication.instance()
        with _batch(ui.bridge):
            _show_page(ui.root, 0, app)
            rows = _queue_rows(ui.root, app)
            assert [row["queue.rowAction"].property("text")
                    for row in rows] == ["Remove", "Cancel", "Remove"]

            _press(rows[2]["queue.rowAction"])
            app.processEvents()
            assert [job.id for job in ui.bridge._queue] == [1, 2]

    def test_the_running_row_carries_the_live_bar(self, ui):
        """The bar reads the scalar property, so the row model never rebuilds for it."""
        app = QGuiApplication.instance()
        with _batch(ui.bridge) as jobs:
            _show_page(ui.root, 0, app)
            bridge = ui.bridge
            jobs[1].progress = 40          # the active job, so the scalar follows
            bridge.downloadChanged.emit()
            _show_page(ui.root, 0, app)
            assert bridge.downloadProgress == 40

            rows = _queue_rows(ui.root, app)
            track = rows[1]["queue.rowProgress"]
            assert track.property("visible") is True
            assert rows[0]["queue.rowProgress"].property("visible") is False
            # The bar eases to its target over 180ms, so the settled width is
            # what has to be measured.
            QTest.qWait(300)
            app.processEvents()
            assert rows[1]["queue.rowProgressFill"].property("width") == pytest.approx(
                track.property("width") * 0.4, abs=1.0)

    def test_a_failed_row_keeps_its_reason(self, ui):
        """The batch carries on after a failure, so the reason belongs on the row."""
        app = QGuiApplication.instance()
        with _batch(ui.bridge) as jobs:
            jobs[1].state = FAILED
            jobs[1].video_outcome = "failed"
            jobs[1].error = "HTTP Error 403: Forbidden"
            ui.bridge.queueChanged.emit()
            _show_page(ui.root, 0, app)
            row = _queue_rows(ui.root, app)[1]
            assert row["queue.rowDetail"].property("text").startswith("Failed")
            assert row["queue.rowError"].property("visible") is True
            assert row["queue.rowError"].property("text") == "HTTP Error 403: Forbidden"

    def test_clearing_the_queue_leaves_only_the_running_job(self, ui):
        app = QGuiApplication.instance()
        with _batch(ui.bridge):
            _show_page(ui.root, 0, app)
            _press(_find(ui.root, "queue.clearButton"))
            app.processEvents()
            assert [job.id for job in ui.bridge._queue] == [2]
            assert len(_queue_rows(ui.root, app)) == 1


class TestSubtitleTrackPicker:
    def test_none_is_always_offered_first(self, ui):
        # With the shipped default ("none"), an inspection preselects nothing,
        # so the picker rests on its None row.
        picker = _find(ui.root, "download.subtitleTracks")
        assert picker.property("selected") == ""

    def test_every_track_is_listed(self, ui):
        bridge = ui.bridge
        codes = [t["code"] for t in bridge.subtitleTracks]
        assert codes.count("ja") == 2  # manual and auto are separate
        assert "en" in codes
        assert bridge.hasSubtitleTracks is True

    def test_selecting_a_track_updates_the_picker(self, ui):
        bridge = ui.bridge
        picker = _find(ui.root, "download.subtitleTracks")
        saved = bridge.selectedSubtitleTrack
        try:
            bridge.selectedSubtitleTrack = "en"
            assert picker.property("selected") == "en"
            assert bridge.selectedSubtitleLabel == "English · manual"
            bridge.selectedSubtitleTrack = ""
            assert picker.property("selected") == ""
            assert bridge.selectedSubtitleLabel == "None — video only"
        finally:
            bridge.selectedSubtitleTrack = saved

    def test_subtitle_only_button_needs_a_track(self, ui):
        bridge = ui.bridge
        button = _find(ui.root, "download.subtitleOnlyButton")
        saved = bridge.selectedSubtitleTrack
        try:
            bridge.selectedSubtitleTrack = ""
            assert button.property("enabled") is False
            bridge.selectedSubtitleTrack = "ja"
            assert button.property("enabled") is True
        finally:
            bridge.selectedSubtitleTrack = saved

    def test_the_selected_row_tints_whichever_row_it_is(self, ui):
        """Review F4: the English row once read a stale ``data`` identifier.

        ``Item.data`` is the default property list, so ``data.code`` was always
        undefined and the row never tinted, while its radio dot and label did —
        two halves of one selection state disagreeing.
        """
        none_row = _find_item(ui.root, "download.trackNone")
        english_row = _find_item(ui.root, "download.trackEnglish")
        saved = ui.bridge.selectedSubtitleTrack
        app = QGuiApplication.instance()
        try:
            ui.bridge.selectedSubtitleTrack = ""
            app.processEvents()
            assert none_row.property("color") != english_row.property("color"), (
                "the checked row must look different from its neighbour")
            none_when_checked = none_row.property("color")

            ui.bridge.selectedSubtitleTrack = "en"
            app.processEvents()
            assert none_row.property("color") != english_row.property("color"), (
                "the checked row must look different from its neighbour")
            assert none_row.property("color") != none_when_checked, (
                "the tint did not move with the selection")
        finally:
            ui.bridge.selectedSubtitleTrack = saved

    def test_more_tracks_is_a_bounded_themed_combo(self, ui):
        """Review F5: the raw ComboBox opened a Basic popup and bound its index."""
        more = _find_item(ui.root, "download.subtitleMore")
        assert more.metaObject().className().startswith("BoundComboBox")
        saved = ui.bridge.selectedSubtitleTrack
        app = QGuiApplication.instance()
        try:
            # "en" is not in this list, so the placeholder shows, not a blank.
            ui.bridge.selectedSubtitleTrack = "en"
            app.processEvents()
            assert more.property("displayText") == "More subtitle tracks…"
            assert more.property("currentIndex") == -1

            # A track that IS in the list mirrors the store after the store
            # changed underneath it - the binding-safe path.
            ui.bridge.selectedSubtitleTrack = "ja"
            app.processEvents()
            assert more.property("currentIndex") == 0
            assert more.property("displayText") == "Japanese · manual"
        finally:
            ui.bridge.selectedSubtitleTrack = saved


def _palette_names(palette) -> list:
    """The commands an open palette offers, rebuilt as it would be for a user."""
    _call(palette, "open")
    try:
        return [row["name"] for row in palette.property("entries").toVariant()]
    finally:
        _call(palette, "close")


class TestCommandPalette:
    def test_palette_is_closed_initially(self, ui):
        palette = _find(ui.root, "commandPalette")
        assert palette.property("visible") is False

    def test_palette_lists_navigation_and_download_actions(self, ui):
        palette = _find(ui.root, "commandPalette")
        _call(palette, "open")
        try:
            assert palette.property("visible") is True
            names = [row["name"] for row in palette.property("entries").toVariant()]
        finally:
            _call(palette, "close")
        assert "Go to Download" in names
        assert "Download" in names
        assert "Fetch subtitle only" in names

    def test_a_running_job_adds_commands_instead_of_replacing_them(self, ui):
        """The palette used to swap the whole download set for a Cancel.

        With a queue, a running job is not a locked form: the batch commands
        stay offered and Cancel joins them.
        """
        palette = _find(ui.root, "commandPalette")
        with _batch(ui.bridge):
            names = _palette_names(palette)
            for name in ("Inspect formats", "Add to queue",
                         "Fetch subtitle only", "Cancel download"):
                assert name in names, names

    def test_a_waiting_queue_is_offered_as_work_to_start(self, ui):
        app = QGuiApplication.instance()
        palette = _find(ui.root, "commandPalette")
        bridge = ui.bridge
        saved = (bridge._download_running, bridge._active, list(bridge._queue))
        bridge._queue = [QueueJob(id=7, url=bridge._url, title="Waiting job")]
        bridge._active = None
        bridge._download_running = False
        bridge.queueChanged.emit()
        bridge.downloadChanged.emit()
        try:
            app.processEvents()
            names = _palette_names(palette)
            assert "Start queue" in names, names
            assert "Clear queue" in names, names
            assert "Cancel download" not in names, names
        finally:
            (bridge._download_running, bridge._active, bridge._queue) = saved
            bridge.queueChanged.emit()
            bridge.downloadChanged.emit()
            app.processEvents()

    def test_activating_a_navigation_entry_switches_the_page(self, ui):
        palette = _find(ui.root, "commandPalette")
        stack = _stack(ui.root)
        _call(palette, "open")
        palette.navigateRequested.emit(2)
        assert stack.property("currentIndex") == 2
        _call(palette, "close")
        ui.root.setProperty("currentPage", 0)

    def test_palette_offers_the_log_and_the_newest_file(self, ui):
        """Both were engine capabilities with no way in until the redesign."""
        palette = _find(ui.root, "commandPalette")
        _call(palette, "open")
        try:
            rows = palette.property("entries").toVariant()
        finally:
            _call(palette, "close")
        by_name = {row["name"]: row for row in rows}
        assert "View log" in by_name, sorted(by_name)
        assert "Open last downloaded file" in by_name, sorted(by_name)
        assert by_name["View log"]["action"] == "view_log"
        assert by_name["Open last downloaded file"]["action"] == "open_last"

    def test_a_row_is_a_name_and_a_chord_and_nothing_else(self, ui):
        """The reference row is one line: name left, chord right.

        ``detail`` still rides in the entry dict as search fuel, so the point of
        this test is that it never reaches the screen.
        """
        app = QGuiApplication.instance()
        palette = _find(ui.root, "commandPalette")
        _call(palette, "open")
        app.processEvents()
        QTest.qWait(60)
        app.processEvents()
        try:
            list_view = _find_item(ui.root, "palette.list")
            texts = _shown_text(_visual_tree(list_view))
            assert "Go to Download" in texts, texts
            assert "Ctrl+1" in texts, texts
            for detail in ("Inspect a URL and download", "Everything the app has reported"):
                assert detail not in texts, detail

            # A chordless entry paints exactly one label.
            name = [item for item in _visual_tree(list_view)
                    if item.property("text") == "View log"]
            assert name, texts
            node = name[0]
            while node.parentItem().parentItem() is not list_view:
                node = node.parentItem()
            assert _shown_text(_visual_tree(node)) == ["View log"]
        finally:
            _call(palette, "close")
            app.processEvents()

    def test_the_search_row_is_the_dialogs_flush_line(self, ui):
        search = _find(ui.root, "palette.search")
        assert float(search.property("height")) == 52.0
        assert float(search.property("leftPadding")) == 16.0

    def test_choosing_view_log_raises_the_log_dialog(self, ui):
        app = QGuiApplication.instance()
        palette = _find(ui.root, "commandPalette")
        dialog = _find(ui.root, "logDialog")
        assert dialog.property("visible") is False
        palette.actionRequested.emit("view_log")
        app.processEvents()
        try:
            assert dialog.property("visible") is True
        finally:
            _call(dialog, "close")
            app.processEvents()


class TestLogDialog:
    def test_it_starts_closed(self, ui):
        assert _find(ui.root, "logDialog").property("visible") is False

    def test_opening_it_counts_the_log_and_focuses_close(self, ui):
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        with _log_lines(ui, "ERROR: HTTP Error 403: Forbidden while fetching\n"
                           "WARNING: unable to download the thumbnail\n"):
            _call(dialog, "open")
            app.processEvents()
            try:
                assert dialog.property("visible") is True
                assert (_find(ui.root, "log.counts").property("text")
                        == "1 warnings · 1 errors")
                body = str(_find(ui.root, "log.text").property("text"))
                assert "HTTP Error 403" in body
                focused = _focused_item(ui.root.contentItem())
                assert focused is not None and focused.objectName() == "log.close"
            finally:
                _call(dialog, "close")
                app.processEvents()

    def test_an_empty_log_says_so(self, ui):
        bridge = ui.bridge
        dialog = _find(ui.root, "logDialog")
        saved = (bridge._log_text, bridge._log_error_count, bridge._log_warn_count)
        bridge.clearLog()
        _call(dialog, "open")
        QGuiApplication.instance().processEvents()
        try:
            assert _find(ui.root, "log.text").property("text") == "(empty)"
        finally:
            _call(dialog, "close")
            (bridge._log_text, bridge._log_error_count,
             bridge._log_warn_count) = saved
            bridge.logTextChanged.emit()

    def test_the_body_is_capped_and_the_footer_stays_inside_the_panel(self, ui):
        """A long log used to push the buttons out of the dialog.

        ``anchors.margins`` is not part of a Layout's implicit height, so a panel
        sized from ``column.implicitHeight`` alone lost its own padding.
        """
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        with _log_lines(ui, "".join(f"line {i} of the log\n" for i in range(120))):
            _call(dialog, "open")
            app.processEvents()
            try:
                scroll = _find_item(ui.root, "log.scroll")
                assert float(scroll.property("height")) <= 320.0
                # The ColumnLayout is the scroll's visual parent; the panel is
                # the layout's, and it is the panel that has to hold the footer.
                panel = scroll.parentItem().parentItem()
                close = _find_item(ui.root, "log.close")
                bottom = (float(close.mapToItem(panel, 0, 0).y())
                          + float(close.property("height")))
                assert bottom <= float(panel.property("height")) - 10, bottom
                surface = ui.root.contentItem()
                panel_bottom = (float(panel.mapToItem(surface, 0, 0).y())
                                + float(panel.property("height")))
                assert panel_bottom <= float(surface.property("height")), panel_bottom
            finally:
                _call(dialog, "close")
                app.processEvents()

    def test_copy_and_clear_reach_the_bridge(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        with _log_lines(ui, "ERROR: HTTP Error 403: Forbidden while fetching\n"):
            _call(dialog, "open")
            app.processEvents()
            try:
                _press(_find(ui.root, "log.copy"))
                app.processEvents()
                assert QGuiApplication.clipboard().text() == bridge.logText
                _press(_find(ui.root, "log.clear"))
                app.processEvents()
                assert bridge.logText == ""
                assert _find(ui.root, "log.text").property("text") == "(empty)"
                assert bridge.logErrorCount == 0
            finally:
                _call(dialog, "close")
                app.processEvents()

    def test_escape_closes_it(self, ui):
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        _call(dialog, "open")
        app.processEvents()
        QTest.keyClick(ui.root, Qt.Key_Escape)
        app.processEvents()
        assert dialog.property("visible") is False

    def test_clicking_the_scrim_closes_it(self, ui):
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        _call(dialog, "open")
        app.processEvents()
        surface = ui.root.contentItem()
        # Bottom-left corner: inside the window, outside the panel, so only the
        # scrim can take this click.
        _click_at(ui.root, 20.0, float(surface.property("height")) - 20.0)
        app.processEvents()
        assert dialog.property("visible") is False

    def test_the_status_bar_counts_are_the_way_in(self, ui):
        """The reference turns the footer's two counts into buttons."""
        app = QGuiApplication.instance()
        dialog = _find(ui.root, "logDialog")
        with _log_lines(ui, "ERROR: HTTP Error 403: Forbidden while fetching\n"
                           "WARNING: unable to download the thumbnail\n"):
            errors = _find(ui.root, "chrome.logErrors")
            warnings = _find(ui.root, "chrome.logWarnings")
            assert str(errors.property("text")) == "1 error"
            assert str(warnings.property("text")) == "1 warning"
            _press(errors)
            app.processEvents()
            try:
                assert dialog.property("visible") is True
            finally:
                _call(dialog, "close")
                app.processEvents()


class TestApplicationShortcuts:
    def test_the_shell_binds_sequences_to_the_notified_map(self):
        """``shortcutFor()`` is a slot: reading it once froze every chord.

        The ten ``sequence:`` lines are counted so a new action cannot be added
        to the map without being given a ``Shortcut`` too.
        """
        source = (QML_DIR / "Main.qml").read_text(encoding="utf-8").splitlines()
        bound = [line.strip() for line in source if "sequence:" in line]
        assert len(bound) == 10, bound
        assert all("appBridge.shortcutMap." in line for line in bound), bound

    def test_re_recording_a_chord_moves_the_live_shortcut(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        chords = dict(bridge.shortcutMap)
        assert chords["goto_download"] == "Ctrl+1"
        assert "Ctrl+1" in _app_shortcuts(ui.root)
        try:
            assert bridge.setShortcut("goto_download", "Ctrl+8") == ""
            app.processEvents()
            live = _app_shortcuts(ui.root)
        finally:
            bridge.resetAllShortcuts()
            app.processEvents()
        assert "Ctrl+8" in live, live
        assert "Ctrl+1" not in live, live

    def test_an_open_palette_silences_every_chord_but_its_own(self, ui):
        app = QGuiApplication.instance()
        bridge = ui.bridge
        chords = set(bridge.shortcutMap.values())
        palette = _find(ui.root, "commandPalette")
        _call(palette, "open")
        app.processEvents()
        try:
            live = _app_shortcuts(ui.root)
            own = bridge.shortcutMap["palette"]
            quieted = [seq for seq in chords if seq != own]
            assert all(live[seq] is False for seq in quieted), live
            # Ctrl+K stays live while the palette is up, so it can close it.
            assert live[own] is True, live
        finally:
            _call(palette, "close")
            app.processEvents()
        live = _app_shortcuts(ui.root)
        assert all(live[seq] is True for seq in chords), live

    def test_an_open_log_dialog_silences_the_palette_chord_too(self, ui):
        app = QGuiApplication.instance()
        bridge = ui.bridge
        dialog = _find(ui.root, "logDialog")
        _call(dialog, "open")
        app.processEvents()
        try:
            live = _app_shortcuts(ui.root)
            assert all(live[seq] is False for seq in set(bridge.shortcutMap.values())
                       if seq), live
        finally:
            _call(dialog, "close")
            app.processEvents()

    def test_recording_a_chord_silences_them_all(self, ui):
        """While Settings is capturing a key, Ctrl+1 must not navigate away."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        ui.root.setProperty("capturingShortcuts", True)
        app.processEvents()
        try:
            live = _app_shortcuts(ui.root)
            assert all(live[seq] is False for seq in set(bridge.shortcutMap.values())
                       if seq), live
        finally:
            ui.root.setProperty("capturingShortcuts", False)
            app.processEvents()


class TestLibraryPage:
    def test_empty_state_when_nothing_was_downloaded(self, ui):
        bridge = ui.bridge
        saved = list(bridge._history)
        try:
            bridge.clearHistory()
            assert bridge.historyCount == 0
            table = _find(ui.root, "library.table")
            assert table.property("count") == 0
        finally:
            bridge._history = saved
            bridge.historyChanged.emit()

    def test_rows_render_the_downloaded_file(self, ui, tmp_path):
        """The store dict is not the row; assert what the delegate painted.

        ``findChildren`` cannot see a ``ListView`` delegate, so the rendered
        subtree is walked through ``childItems()``.
        """
        bridge = ui.bridge
        app = QGuiApplication.instance()
        path = tmp_path / "A test video [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        with _one_history_row(ui, path):
            try:
                assert _find(ui.root, "library.table").property("count") == 1
                row = bridge.history[0]
                assert row["detail"]  # format label, shown under the name
                assert "thumbnail" in row and "duration" in row

                items = _library_row(ui.root, app, path.name)
                texts = _shown_text(items)
                assert path.name in texts, texts
                assert any(t == row["sizeText"] for t in texts), texts
                assert not any("missing from disk" in t for t in texts)

                actions = [item for item in items
                           if item.metaObject().className().startswith("AppButton")]
                assert actions, "a rendered row must expose its actions"
                assert all(bool(item.property("enabled")) for item in actions)
            finally:
                _leave_library(ui, app)

    def test_a_row_whose_file_vanished_says_so_and_disables_actions(self, ui, tmp_path):
        """The warning is a word, not only a colour, so greyscale still reads it."""
        bridge = ui.bridge
        app = QGuiApplication.instance()
        path = tmp_path / "Gone [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        with _one_history_row(ui, path):
            try:
                items = _library_row(ui.root, app, path.name)
                assert not any("missing from disk" in t for t in _shown_text(items))

                path.unlink()
                bridge.historyChanged.emit()
                items = _library_row(ui.root, app, path.name)
                texts = _shown_text(items)
                actions = [item for item in items
                           if item.metaObject().className().startswith("AppButton")]
                assert any("missing from disk" in t for t in texts), texts
                by_key = {(str(item.property("text") or "") or
                           str(item.property("tooltip") or "")): item for item in actions}
                assert "Open" in by_key and "Redownload" in by_key, sorted(by_key)
                assert not bool(by_key["Open"].property("enabled")), "Open"
                # A vanished file is exactly what redownload is for, so that
                # action stays live even when Open is not.
                assert bool(by_key["Redownload"].property("enabled")), "Redownload"
            finally:
                _leave_library(ui, app)


class TestClearHistoryDialog:
    """The confirmation that empties the library, drawn as one padded block.

    A ``Popup`` lays a Dialog's ``header`` and ``footer`` out *outside* its
    ``padding``, flush with the border, which is where the review saw the
    heading touching the top edge and the buttons the bottom and right ones.
    Both bands are suppressed, so every inset and gap is measurable geometry.
    """

    @contextlib.contextmanager
    def _opened(self, ui, tmp_path):
        """The dialog, opened by the button that owns it, over a one-row library."""
        app = QGuiApplication.instance()
        path = tmp_path / "Kept [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 1024)
        with _one_history_row(ui, path):
            _show_page(ui.root, 1, app)
            dialog = _find(ui.root, "library.clearDialog")
            _press(_find(ui.root, "library.clearButton"))
            app.processEvents()
            assert bool(dialog.property("visible")), \
                "the Clear history button must open the dialog"
            try:
                yield dialog
            finally:
                if bool(dialog.property("visible")):
                    _call(dialog, "close")
                app.processEvents()
                _leave_library(ui, app)

    def test_every_edge_gets_the_same_inset(self, ui, tmp_path):
        with self._opened(ui, tmp_path) as dialog:
            surface = dialog.property("background")
            padding = float(dialog.property("padding"))
            title = _place(_find_item(ui.root, "library.clearTitle"), surface)
            confirm = _place(_find_item(ui.root, "library.clearConfirm"), surface)
            insets = (title[1], title[0],
                      float(surface.property("height")) - confirm[1] - confirm[3],
                      float(surface.property("width")) - confirm[0] - confirm[2])
            assert insets == pytest.approx((padding,) * 4, abs=0.5), insets

    def test_the_default_header_and_footer_bands_are_suppressed(self, ui, tmp_path):
        """Both bands would sit outside ``padding``, so nothing may live there."""
        with self._opened(ui, tmp_path) as dialog:
            for band in ("header", "footer"):
                item = dialog.property(band)
                assert isinstance(item, QQuickItem), band
                assert not bool(item.property("visible")), band
                assert float(item.property("height")) == 0.0, band

    def test_the_heading_hugs_its_sentence_and_the_actions_do_not(self, ui, tmp_path):
        """``xs`` below the title, ``lg`` below the body — and one gap each."""
        with self._opened(ui, tmp_path) as dialog:
            surface = dialog.property("background")
            title = _find_item(ui.root, "library.clearTitle")
            body = _find_item(ui.root, "library.clearBody")
            cancel = _find_item(ui.root, "library.clearCancel")
            heading_gap = _place(body, surface)[1] - _place(title, surface)[1] \
                - float(title.property("height"))
            action_gap = _place(cancel, surface)[1] - _place(body, surface)[1] \
                - float(body.property("height"))
            assert action_gap > heading_gap, (heading_gap, action_gap)
            assert action_gap >= 2 * heading_gap, (heading_gap, action_gap)

    def test_the_two_actions_are_the_same_size(self, ui, tmp_path):
        with self._opened(ui, tmp_path):
            cancel = _find_item(ui.root, "library.clearCancel")
            confirm = _find_item(ui.root, "library.clearConfirm")
            assert (float(cancel.property("width")), float(cancel.property("height"))) \
                == pytest.approx((float(confirm.property("width")),
                                  float(confirm.property("height"))), abs=0.5)

    def test_focus_lands_on_cancel_so_enter_is_safe(self, ui, tmp_path):
        """Enter dismisses; it must never be the destructive one that answers."""
        app = QGuiApplication.instance()
        bridge = ui.bridge
        with self._opened(ui, tmp_path) as dialog:
            focused = _focused_item(ui.root.contentItem())
            assert focused is not None and focused.objectName() == "library.clearCancel", \
                focused
            QTest.keyClick(ui.root, Qt.Key_Return)
            app.processEvents()
            assert not bool(dialog.property("visible"))
            assert bridge.historyCount == 1, "Enter must not clear the library"

    @pytest.mark.parametrize("dismiss", ["cancel", "escape"])
    def test_the_safe_doors_both_leave_the_rows_alone(self, ui, tmp_path, dismiss):
        app = QGuiApplication.instance()
        bridge = ui.bridge
        with self._opened(ui, tmp_path) as dialog:
            if dismiss == "cancel":
                _press(_find(ui.root, "library.clearCancel"))
            else:
                QTest.keyClick(ui.root, Qt.Key_Escape)
            app.processEvents()
            assert not bool(dialog.property("visible"))
            assert bridge.historyCount == 1

    def test_confirming_is_the_only_way_to_empty_the_library(self, ui, tmp_path):
        app = QGuiApplication.instance()
        bridge = ui.bridge
        with self._opened(ui, tmp_path) as dialog:
            _press(_find(ui.root, "library.clearConfirm"))
            app.processEvents()
            assert not bool(dialog.property("visible"))
            assert bridge.historyCount == 0


class TestSettingsPage:
    def test_appearance_controls_exist(self, ui):
        _find(ui.root, "settings.theme")
        _find(ui.root, "settings.comfortable")
        _find(ui.root, "settings.reducedMotion")
        _find(ui.root, "settings.defaultSubtitleTrack")
        _find(ui.root, "settings.filenameTemplate")

    def test_the_switch_focus_ring_is_concentric(self, ui):
        """Review F9: the ring used to be ``radius: 12``.

        Twelve was right only because the track happened to be 18 tall and the
        ring inset by -3. Expressed as ``track.radius + 3`` it stays a grown
        pill whatever the switch becomes, and the token rule keeps one literal
        from drifting out of step with ``Theme.radiusLg``.
        """
        switch = _find_item(ui.root, "settings.comfortable")
        track = _find_item(switch, "appSwitch.track")
        ring = _find_item(switch, "appSwitch.ring")
        assert float(track.property("radius")) == float(track.property("height")) / 2
        assert float(ring.property("radius")) == float(track.property("radius")) + 3

    def test_theme_toggle_is_wired(self, ui):
        saved = ui.bridge.themeName
        try:
            ui.bridge.toggleTheme()
            assert ui.bridge.themeName != saved
        finally:
            ui.bridge.themeName = saved

    def test_default_subtitle_choice_round_trips(self, ui):
        bridge = ui.bridge
        saved = bridge.defaultSubtitleTrack
        try:
            bridge.defaultSubtitleTrack = "auto"
            assert bridge.defaultSubtitleTrack == "auto"
        finally:
            bridge.defaultSubtitleTrack = saved

    def test_preferred_format_controls_round_trip(self, ui):
        bridge = ui.bridge
        saved = (bridge.preferredCodec, bridge.preferredResolution)
        try:
            _find(ui.root, "settings.preferredCodec")
            _find(ui.root, "settings.preferredResolution")
            bridge.preferredCodec = "vp9"
            bridge.preferredResolution = "720"
            assert bridge.preferredCodec == "vp9"
            assert bridge.preferredResolution == "720"
            # "best" and "no preference" behave alike, so they collapse.
            bridge.preferredResolution = "best"
            assert bridge.preferredResolution == ""
        finally:
            bridge.preferredCodec = saved[0]
            bridge.preferredResolution = saved[1]


class TestKeyboardReachability:
    """Review F6: if Tab cannot reach it, the control does not exist for some users.

    Only ``activeFocusOnTab`` puts an item in the chain; a ``MouseArea`` does
    not, however complete its ``Accessible`` properties look. The items that
    used to be plain ``Item``/``Rectangle`` - rail destinations, the palette
    button, format rows, the two always-visible subtitle rows and the accent
    swatches - are exactly the ones a pointer-only review misses.

    Keys go to the window because that is how the offscreen platform delivers
    focus: the item with ``activeFocus`` receives them, same as on a real one.
    """

    REQUIRED = {
        0: ("rail.destination.0", "rail.destination.1", "rail.destination.2",
            "rail.palette", "download.bestCell", "download.formatRow.1",
            "download.trackNone", "download.trackEnglish",
            "download.subtitleMore"),
        2: ("settings.accent.iris", "settings.accent.azure",
            "settings.accent.mint"),
    }

    def _tab_stops(self, ui, page: int, presses: int = 60) -> list[str]:
        app = QGuiApplication.instance()
        _show_page(ui.root, page, app)
        surface = ui.root.contentItem()
        stops = []
        for _ in range(presses):
            QTest.keyClick(ui.root, Qt.Key_Tab)
            app.processEvents()
            focused = _focused_item(surface)
            if focused is not None:
                stops.append(focused.objectName())
        return stops

    @pytest.mark.parametrize("page", sorted(REQUIRED))
    def test_custom_controls_are_tab_stops(self, ui, page):
        app = QGuiApplication.instance()
        try:
            seen = set(self._tab_stops(ui, page))
            missing = [name for name in self.REQUIRED[page] if name not in seen]
            assert missing == [], f"not reachable with Tab: {missing}"
        finally:
            _leave_library(ui, app)

    def test_return_on_the_rail_changes_page(self, ui):
        app = QGuiApplication.instance()
        try:
            assert _focus_by_tabbing(ui, "rail.destination.1"), "rail stop missing"
            QTest.keyClick(ui.root, Qt.Key_Return)
            app.processEvents()
            assert ui.root.property("currentPage") == 1
        finally:
            ui.root.setProperty("currentPage", 0)
            app.processEvents()

    def test_return_on_a_subtitle_row_selects_it(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        saved = bridge.selectedSubtitleTrack
        try:
            _show_page(ui.root, 0, app)
            assert _focus_by_tabbing(ui, "download.trackEnglish"), "row stop missing"
            bridge.selectedSubtitleTrack = ""
            QTest.keyClick(ui.root, Qt.Key_Space)
            app.processEvents()
            assert bridge.selectedSubtitleTrack == "en"
        finally:
            bridge.selectedSubtitleTrack = saved

    def test_return_on_a_format_row_picks_that_format(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        row = bridge.formatRows[1]
        saved = (bridge.selectedCodec, bridge.selectedResolution)
        try:
            _show_page(ui.root, 0, app)
            assert _focus_by_tabbing(ui, "download.formatRow.1"), "row stop missing"
            QTest.keyClick(ui.root, Qt.Key_Return)
            app.processEvents()
            assert bridge.selectedCodec == row["codec"]
            assert str(bridge.selectedResolution) == str(row["resolution"])
        finally:
            bridge.selectedCodec, bridge.selectedResolution = saved

    def test_return_on_an_accent_swatch_changes_the_accent(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        choices = [c["id"] for c in bridge.accentChoices]
        target = next(c for c in choices if c != bridge.accentName)
        saved = bridge.accentName
        try:
            _show_page(ui.root, 2, app)
            assert _focus_by_tabbing(ui, f"settings.accent.{target}"), "swatch missing"
            QTest.keyClick(ui.root, Qt.Key_Return)
            app.processEvents()
            assert bridge.accentName == target
        finally:
            bridge.setAccent(saved)
            _leave_library(ui, app)


class TestMediaThumb:
    """The 16:9 preview keeps its box in every state."""

    def _create(self, ui, **props):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent

        component = QQmlComponent(
            ui.engine,
            QUrl.fromLocalFile(str(QML_DIR / "components" / "MediaThumb.qml")),
        )
        assert component.isReady(), [e.toString() for e in component.errors()]
        item = component.create()
        assert item is not None, [e.toString() for e in component.errors()]
        # Created root objects are QML-garbage-collectible; park this one under
        # the window so it outlives the component wrapper.
        item.setParent(ui.root)
        for name, value in props.items():
            assert item.setProperty(name, value)
        return item

    def test_height_follows_the_sixteen_by_nine_ratio(self, ui):
        thumb = self._create(ui, width=320)
        assert thumb.property("implicitHeight") == 180
        thumb.setProperty("width", 160)
        assert thumb.property("implicitHeight") == 90

    def test_defaults_show_the_placeholder_not_the_pill(self, ui):
        thumb = self._create(ui, width=224)
        assert thumb.property("hasImage") is False
        image = _find(thumb, "mediaThumb.image")
        assert image.property("source").toString() == ""
        assert _find(thumb, "mediaThumb.placeholder").property("visible") is True
        assert _find(thumb, "mediaThumb.durationPill").property("visible") is False

    def test_duration_pill_uses_the_mono_clock(self, ui):
        thumb = self._create(ui, width=224, duration=95)
        pill = _find(thumb, "mediaThumb.durationPill")
        assert pill.property("visible") is True
        label = _find(thumb, "mediaThumb.durationLabel")
        assert label.property("text") == "1:35"


class TestAccentIsNotText:
    """Review F7: raw accent clears 3:1 on its own tint and 4.5 nowhere near it.

    So ``Theme.accent`` may fill a shape (selection dot, rail icon, radio ring)
    but may not be a word's colour where a tint can appear behind it. Checked by
    element: the block a ``color:`` line belongs to decides whether it is text.
    """

    SHAPES = {"Icon", "Rectangle", "Circle"}
    TEXT = re.compile(r'(?<![.\w])color:\s*(?!.*rgba)(?!.*(accentLine|accentSoft|accentInk))'
                      r'[^\n]*\bTheme\.accent\b')
    OPENER = re.compile(r'^\s*(?:\w+\s*:\s*)?([A-Z]\w*)\s*\{')

    def _element_at(self, lines, index) -> str:
        for earlier in range(index, -1, -1):
            match = self.OPENER.match(lines[earlier])
            if match:
                return match.group(1)
        return ""

    def test_no_label_binds_its_color_to_raw_accent(self):
        offenders = []
        for path in QML_DIR.rglob("*.qml"):
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if line.strip().startswith("//") or not self.TEXT.search(line):
                    continue
                element = self._element_at(lines, number - 1)
                if element and element not in self.SHAPES:
                    offenders.append(f"{path.name}:{number} in {element} — {line.strip()}")
        assert offenders == []


class TestNoDefaultChrome:
    """Every control surface must be drawn from ``Theme``, not the Basic style.

    Phase 6's acceptance was "no Basic-styled surface remains". These are the
    code patterns that produce one, kept out of the tree by assertion rather
    than by memory.
    """

    WRAPPERS = {"CompactComboBox.qml", "BoundComboBox.qml"}

    def test_no_control_declares_a_bare_combobox(self):
        bare = re.compile(r"(?<![\w.])ComboBox\s*\{")
        offenders = []
        for path in QML_DIR.rglob("*.qml"):
            if path.name in self.WRAPPERS:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("//"):
                    continue
                if bare.search(line):
                    offenders.append(f"{path.name}: {line.strip()}")
        assert offenders == []

    def test_no_dialog_uses_standard_buttons(self):
        offenders = [
            f"{path.name}: {line.strip()}"
            for path in QML_DIR.rglob("*.qml")
            for line in path.read_text(encoding="utf-8").splitlines()
            if "standardButtons" in line
        ]
        assert offenders == []


class TestNoForeignVocabulary:
    """The downloader must never mention the translator, and vice versa."""

    FORBIDDEN = (
        "translation", "translator", "transcribe", "pipeline",
        "translation agent", "subtitle translator",
    )

    def test_qml_never_mentions_another_app(self):
        offenders = []
        for path in QML_DIR.rglob("*.qml"):
            text = path.read_text(encoding="utf-8").lower()
            for word in self.FORBIDDEN:
                if word in text:
                    offenders.append(f"{path.name}: {word}")
        assert offenders == [], offenders

    def test_python_never_imports_another_app(self):
        root = QML_DIR.parent.parent
        offenders = []
        for path in list(root.glob("*.py")) + list((root / "app").glob("*.py")) + list((root / "src").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "translation_agent" in text or "translation-agent" in text:
                offenders.append(path.name)
        assert offenders == [], offenders


class TestLibraryDrawer:
    """C6: click/keyboard selection opens the 320 px drawer and collapses the
    WHEN + action columns behind it."""

    def test_selecting_a_row_opens_the_drawer_and_collapses_the_columns(self, ui, tmp_path):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        path = tmp_path / "Kept [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        with _one_history_row(ui, path):
            try:
                _show_page(ui.root, 1, app)
                drawer = _find_item(ui.root, "library.drawer")
                assert not bool(drawer.property("visible"))

                bridge.selectHistory(0)
                app.processEvents()
                QTest.qWait(60)
                app.processEvents()
                assert bool(drawer.property("visible"))
                name = _find_item(ui.root, "library.drawerName")
                assert path.name in str(name.property("text"))
                for control in ("library.drawerOpen", "library.drawerFolder",
                                "library.drawerCopy", "library.drawerRedownload",
                                "library.drawerRemove"):
                    _find_item(ui.root, control)

                page = _find_item(ui.root, "libraryPage")

                # `.libwrap.has .lib>:nth-child(n+4){display:none}` - the row
                # gives up its WHEN value and its inline actions to the drawer,
                # and the reference lists carry no column headers at all. The
                # delegate is rebuilt when the selection changes, so the row is
                # looked up again instead of being held on to.
                def when_shown() -> bool:
                    found = [item for item in _visual_tree(page)
                             if item.objectName() == "library.when.0"]
                    assert found, "the row's WHEN value disappeared entirely"
                    return bool(found[0].property("visible"))

                assert when_shown() is False

                bridge.selectHistory(-1)
                app.processEvents()
                QTest.qWait(60)
                app.processEvents()
                assert not bool(drawer.property("visible"))
                assert when_shown() is True
            finally:
                _leave_library(ui, app)

    def test_return_on_a_row_opens_the_drawer_too(self, ui, tmp_path):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        path = tmp_path / "Keys [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        with _one_history_row(ui, path):
            try:
                items = _library_row(ui.root, app, path.name)
                items[0].forceActiveFocus()
                app.processEvents()
                QTest.qWait(40)
                QTest.keyClick(ui.root, Qt.Key_Return)
                app.processEvents()
                assert bridge.selectedHistoryIndex == 0
                QTest.keyClick(ui.root, Qt.Key_Return)
                app.processEvents()
                assert bridge.selectedHistoryIndex == -1
            finally:
                _leave_library(ui, app)

    def test_delete_on_a_focused_row_removes_it_from_the_list(self, ui, tmp_path):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        path = tmp_path / "Doomed [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        with _one_history_row(ui, path):
            try:
                items = _library_row(ui.root, app, path.name)
                items[0].forceActiveFocus()
                app.processEvents()
                QTest.qWait(40)
                QTest.keyClick(ui.root, Qt.Key_Delete)
                app.processEvents()
                QTest.qWait(40)
                app.processEvents()
                assert bridge.historyCount == 0
                assert path.exists(), "deleting a row must not delete the file"
            finally:
                _leave_library(ui, app)


class TestFailureBanner:
    """C5: the diagnosis has words, survives to be read, and leaves on
    request."""

    def test_a_failure_raises_the_banner_and_dismissal_lowers_it(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 0, app)
        banner = _find_item(ui.root, "download.failureBanner")
        assert not bool(banner.property("visible"))

        bridge._set_failure("network", "The network gave up",
                            "HTTP Error 503 while fetching the video",
                            "Check your connection and retry.")
        app.processEvents()
        QTest.qWait(60)
        app.processEvents()
        assert bool(banner.property("visible"))
        title = _find_item(ui.root, "download.failureTitle")
        assert str(title.property("text")) == "The network gave up"
        texts = [str(item.property("text") or "") for item in _visual_tree(banner)
                 if item.property("text") is not None
                 and bool(item.property("visible"))]
        assert any("503" in t for t in texts), texts
        assert any("retry" in t.lower() for t in texts), texts

        retry = _find_item(ui.root, "download.failureRetry")
        assert bool(retry.property("enabled")) is bridge.canDownload

        _press(_find_item(ui.root, "download.failureDismiss"))
        app.processEvents()
        QTest.qWait(60)
        app.processEvents()
        assert bridge.failureActive is False
        assert not bool(banner.property("visible"))

    def test_a_fresh_inspection_clears_a_stale_banner(self, ui):
        bridge = ui.bridge
        bridge._set_failure("error", "The download failed", "detail", "remedy")
        assert bridge.failureActive
        bridge._info_gen += 1
        bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(_info_payload()))
        QGuiApplication.instance().processEvents()
        assert bridge.failureActive is False


class TestShortcutRecorder:
    """C7: Record arms the window catcher; the next chord replaces the old
    one, a collision refuses, Escape gives up."""

    def _button(self, ui, name):
        """Reach a shortcut-row button through the page's visual tree.

        The rows are Repeater delegates - invisible to ``findChild``.
        """
        page = _find_item(ui.root, "settingsPage")
        hit = [item for item in _visual_tree(page) if item.objectName() == name]
        assert hit, f"{name} not rendered on the Settings page"
        return hit[0]

    def _disarm(self, ui):
        if ui.root.property("capturingShortcuts"):
            ui.root.setProperty("capturingShortcuts", False)
            ui.root.setProperty("capturingAction", "")
            ui.root.setProperty("captureMessage", "")

    def _arm(self, ui, action):
        app = QGuiApplication.instance()
        record = self._button(ui, f"settings.shortcut.record.{action}")
        _press(record)
        app.processEvents()
        QTest.qWait(60)
        app.processEvents()
        assert ui.root.property("capturingShortcuts") is True
        assert str(ui.root.property("capturingAction")) == action
        catcher = _find_item(ui.root, "keyCatcher")
        catcher.forceActiveFocus()
        app.processEvents()
        QTest.qWait(40)

    def test_recording_a_free_chord_replaces_it(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 2, app)
        try:
            self._arm(ui, "palette")
            QTest.keyClick(ui.root, Qt.Key_J, Qt.ControlModifier)
            app.processEvents()
            QTest.qWait(60)
            app.processEvents()
            assert ui.root.property("capturingShortcuts") is False
            assert bridge.shortcutMap["palette"] == "Ctrl+J"
        finally:
            bridge.resetAllShortcuts()
            self._disarm(ui)
            _show_page(ui.root, 0, app)

    def test_a_taken_chord_is_refused_out_loud_and_escape_gives_up(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 2, app)
        before = dict(bridge.shortcutMap)
        try:
            self._arm(ui, "inspect")
            QTest.keyClick(ui.root, Qt.Key_1, Qt.ControlModifier)
            app.processEvents()
            QTest.qWait(60)
            app.processEvents()
            # Still recording, with the collision spelled out.
            assert ui.root.property("capturingShortcuts") is True
            message = str(ui.root.property("captureMessage"))
            assert "Ctrl+1" in message, message
            QTest.keyClick(ui.root, Qt.Key_Escape)
            app.processEvents()
            assert ui.root.property("capturingShortcuts") is False
            assert dict(bridge.shortcutMap) == before
        finally:
            self._disarm(ui)
            _show_page(ui.root, 0, app)

    def test_a_lone_modifier_is_half_a_chord_and_is_ignored(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 2, app)
        try:
            self._arm(ui, "palette")
            QTest.keyClick(ui.root, Qt.Key_Control)
            app.processEvents()
            assert ui.root.property("capturingShortcuts") is True
            assert bridge.shortcutMap["palette"] == "Ctrl+K"
            QTest.keyClick(ui.root, Qt.Key_Escape)
            app.processEvents()
            assert ui.root.property("capturingShortcuts") is False
        finally:
            self._disarm(ui)
            _show_page(ui.root, 0, app)


class TestAutosaveAndPreview:
    """C7: the toast blinks when the bridge persists, and the template card
    renders the preview live."""

    def test_the_saved_toast_blinks_on_the_persist_beat(self, ui):
        app = QGuiApplication.instance()
        _show_page(ui.root, 2, app)
        toast = _find_item(ui.root, "settings.savedToast")
        # An earlier test's autosave may have left it lit; the behavior under
        # test is the blink, so start from a known-dark label.
        toast.setProperty("opacity", 0.0)
        ui.bridge.savedToast.emit()
        app.processEvents()
        QTest.qWait(300)
        app.processEvents()
        assert float(toast.property("opacity")) > 0.9
        QTest.qWait(1500)  # the 1.6 s hold expires
        app.processEvents()
        QTest.qWait(300)
        assert float(toast.property("opacity")) == 0.0

    def test_the_template_preview_follows_the_field(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 2, app)
        preview = _find_item(ui.root, "settings.templatePreview")
        original = bridge.filenameTemplate
        try:
            bridge.filenameTemplate = "%(id)s.%(ext)s"
            app.processEvents()
            QTest.qWait(120)
            app.processEvents()
            assert str(preview.property("text")) == "c0mP1l3r.mp4"
        finally:
            bridge.filenameTemplate = original
            app.processEvents()


class TestHeroIdentityChip:
    """C4: the video ID lives in the hero, one click from the clipboard."""

    def test_the_id_chip_shows_the_video_and_copies_it(self, ui):
        bridge = ui.bridge
        app = QGuiApplication.instance()
        _show_page(ui.root, 0, app)
        chip = _find_item(ui.root, "download.heroIdChip")
        assert bool(chip.property("visible"))
        assert bridge.videoId in str(chip.property("text"))

        QGuiApplication.clipboard().setText("untouched")
        position = chip.mapToScene(QPointF(chip.width() / 2.0, chip.height() / 2.0))
        _click_at(ui.root, position.x(), position.y())
        app.processEvents()
        assert QGuiApplication.clipboard().text() == bridge.videoId
        assert bridge.statusMessage == "Video ID copied."


class TestPlaylistCard:
    PLAYLOAD = {
        "title": "My list",
        "uploader": "Some Channel",
        "count": 3,
        "entries": [
            {"id": f"v{i}", "title": f"Video {i}",
             "url": f"https://www.youtube.com/watch?v=v{i}",
             "duration": 61 * i, "index": i}
            for i in range(1, 4)
        ],
    }

    def test_the_card_lists_rows_range_and_enqueue(self, ui, monkeypatch):
        bridge = ui.bridge
        monkeypatch.setattr(bridge, "_start_video_inspection", lambda u: None)
        saved_url = bridge._url
        bridge._url = "https://www.youtube.com/watch?v=a&list=PLx"
        bridge._playlist_gen += 1
        bridge._on_playlist_done(
            f"PLAYLIST:{bridge._playlist_gen}|" + json.dumps(self.PLAYLOAD))
        app = QGuiApplication.instance()
        _show_page(ui.root, 0, app)
        try:
            card = _find_item(ui.root, "download.playlistCard")
            assert bool(card.property("visible"))
            _find(ui.root, "playlist.rangeField")
            _find(ui.root, "playlist.applyRangeButton")
            button = _find(ui.root, "playlist.enqueueButton")
            assert button.property("enabled") is False
            assert "Add 0 to queue" == button.property("text")

            bridge.applyPlaylistRange("1-2")
            app.processEvents()
            assert button.property("enabled") is True
            assert "Add 2 to queue" == button.property("text")

            checks = [c for c in _visual_tree(_find_item(ui.root, "playlist.list"))
                      if c.objectName() == "playlist.rowCheck"]
            assert len(checks) == 3
            assert [bool(c.property("checked")) for c in checks] == [True, True, False]
        finally:
            bridge.clearPlaylist()
            bridge._url = saved_url
            bridge._notify_form_changed()
            app.processEvents()
