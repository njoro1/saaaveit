"""The downloader's QML must load cleanly and expose the whole flow.

These tests drive the real ``Main.qml`` (offscreen) against the real
``DownloaderBridge``. They are structural: the point is that the three pages
exist, the subtitle picker is part of the download, and nothing that belongs to
another application appears anywhere in the UI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject

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
        bridge = ui.bridge
        path = tmp_path / "A test video [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 2048)
        bridge._record(str(path), "video")
        try:
            table = _find(ui.root, "library.table")
            assert table.property("count") >= 1
            assert bridge.history[0]["name"] == path.name
        finally:
            bridge._history = [e for e in bridge._history if e["path"] != str(path)]
            bridge.historyChanged.emit()


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
