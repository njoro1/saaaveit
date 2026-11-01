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
from PySide6.QtCore import QMetaObject, QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from src import media_source

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
    bridge._record(str(path), "video")
    try:
        yield
    finally:
        bridge._history = saved
        bridge.historyChanged.emit()


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

    def test_format_table_shows_rows(self, ui):
        table = _find(ui.root, "download.formatTable")
        assert table.property("objectName") == "download.formatTable"
        assert len(ui.bridge.formatRows) >= 1

    def test_download_button_is_enabled_with_a_selection(self, ui):
        button = _find(ui.root, "download.downloadButton")
        assert ui.bridge.canDownload is True
        assert button.property("enabled") is True

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


class TestSubtitleTrackPicker:
    def test_none_is_always_offered_first(self, ui):
        picker = _find(ui.root, "download.subtitleTracks")
        assert picker.property("selected") == "ja"

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
            bridge.selectedSubtitleTrack = saved or "ja"

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
            assert none_row.property("color").alphaF() > 0.1
            assert english_row.property("color").alphaF() == 0.0

            ui.bridge.selectedSubtitleTrack = "en"
            app.processEvents()
            assert none_row.property("color").alphaF() == 0.0
            assert english_row.property("color").alphaF() > 0.1
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

    def test_activating_a_navigation_entry_switches_the_page(self, ui):
        palette = _find(ui.root, "commandPalette")
        stack = _stack(ui.root)
        _call(palette, "open")
        palette.navigateRequested.emit(2)
        assert stack.property("currentIndex") == 2
        _call(palette, "close")
        ui.root.setProperty("currentPage", 0)


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
                for key in ("Open", "Open folder"):
                    assert key in by_key, sorted(by_key)
                    assert not bool(by_key[key].property("enabled")), key
            finally:
                _leave_library(ui, app)


class TestSettingsPage:
    def test_appearance_controls_exist(self, ui):
        _find(ui.root, "settings.theme")
        _find(ui.root, "settings.comfortable")
        _find(ui.root, "settings.reducedMotion")
        _find(ui.root, "settings.defaultSubtitleTrack")
        _find(ui.root, "settings.filenameTemplate")

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
            "rail.palette", "download.formatRow.0", "download.trackNone",
            "download.trackEnglish", "download.subtitleMore"),
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
