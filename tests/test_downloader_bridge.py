"""The download operation: one action, two legs, two outcomes.

The behaviour these tests pin down is the whole point of the app:

  * the video leg runs first, then the selected subtitle leg,
  * a *failed* video leg still lets the subtitle leg run,
  * each leg reports its own outcome, and the history records what succeeded,
  * cancelling stops the operation and says so,
  * the subtitle preselection follows the persisted default.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from src import store, media_source


def _matrix() -> tuple[dict, dict]:
    return media_source._build_matrix([
        {"format_id": "401", "ext": "mp4", "height": 1080,
         "vcodec": "av01.0.13M.10", "acodec": "none", "tbr": 5000,
         "filesize": 40_000_000, "fps": 30},
        {"format_id": "140", "ext": "m4a", "height": None,
         "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128,
         "filesize": 4_000_000},
    ])[2:]


def _payload(language="ja", tracks=None) -> dict:
    matrix, best = _matrix()
    return {
        "title": "Test video",
        "video_id": "dQw4w9WgXcQ",
        "language": language,
        "codecs": ["av1"],
        "resolutions": [1080],
        "matrix": matrix,
        "best": best,
        "codecs_available": {"av1": True, "vp9": False, "h264": False},
        "subtitle_tracks": tracks if tracks is not None else [
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": False},
        ],
        "default_subtitle_track": "ja" if language == "ja" else "",
    }


def _install(bridge, payload) -> None:
    bridge._info_gen += 1
    bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(payload))


def _set_url(bridge, url: str) -> None:
    """Assign the URL without letting the setter start a real inspection.

    ``DownloaderBridge.url`` calls ``inspect()`` for any non-empty value, which
    spawns a worker that reaches the network. Tests feed synthetic ``INFO:``
    payloads instead, so the setter must be bypassed — otherwise a failing live
    request races the assertions (and, once the bridge is gone, aborts the run
    with ``RuntimeError: Signal source has been deleted``).
    """
    bridge._url = url
    bridge._notify_form_changed()


@pytest.fixture()
def ready(bridge, tmp_path, monkeypatch):
    """A bridge with a URL, an inspected video and a writable temp output dir."""
    _set_url(bridge, "https://example.com/video?v=dQw4w9WgXcQ")
    bridge._download_dir = str(tmp_path)
    _install(bridge, _payload())
    monkeypatch.setattr(media_source, "probe_video_file", lambda path: {})
    return bridge


def _wait(predicate, timeout=8.0) -> bool:
    from PySide6.QtWidgets import QApplication

    deadline = time.time() + timeout
    while time.time() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QApplication.processEvents()
    return bool(predicate())


class TestCombinedDownload:
    def test_video_then_subtitle_and_both_outcomes(self, ready, tmp_path, monkeypatch):
        calls: list[str] = []

        def fake_video(url, selector, out, **kwargs):
            calls.append("video")
            path = tmp_path / "Video [dQw4w9WgXcQ].mp4"
            path.write_bytes(b"v")
            return str(path)

        def fake_sub(url, lang, out, kind="", **kwargs):
            calls.append(f"subtitle:{lang}:{kind}")
            path = tmp_path / "Video [dQw4w9WgXcQ].ja.srt"
            path.write_text("1\n", encoding="utf-8")
            return str(path)

        monkeypatch.setattr(media_source, "download_video", fake_video)
        monkeypatch.setattr(media_source, "download_subtitle", fake_sub)

        ready.download()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert calls == ["video", "subtitle:ja:manual"], calls
        assert ready.videoOutcome == "ok"
        assert ready.subtitleOutcome == "ok"
        assert ready.downloadedVideo.endswith(".mp4")
        assert ready.downloadedSubtitle.endswith(".ja.srt")
        assert ready.downloadProgress == 100
        assert ready.downloadStage == "done"
        assert ready.statusState == "done"

        rows = ready.history
        assert [row["kind"] for row in rows] == ["subtitle", "video"], rows
        assert all(row["exists"] for row in rows)

    def test_a_failed_video_leg_does_not_suppress_the_subtitle(
        self, ready, tmp_path, monkeypatch
    ):
        calls: list[str] = []

        def fake_video(url, selector, out, **kwargs):
            calls.append("video")
            raise RuntimeError("HTTP Error 403: Forbidden")

        def fake_sub(url, lang, out, kind="", **kwargs):
            calls.append("subtitle")
            path = tmp_path / "Video [dQw4w9WgXcQ].ja.srt"
            path.write_text("1\n", encoding="utf-8")
            return str(path)

        monkeypatch.setattr(media_source, "download_video", fake_video)
        monkeypatch.setattr(media_source, "download_subtitle", fake_sub)

        ready.download()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert calls == ["video", "subtitle"], calls
        assert ready.videoOutcome == "failed"
        assert ready.subtitleOutcome == "ok"
        assert "403" in ready.downloadError
        # The subtitle still landed, and the status line says what succeeded.
        assert ready.downloadedSubtitle != ""
        assert ready.history and ready.history[0]["kind"] == "subtitle"
        assert "subtitle" in ready.statusMessage.lower()

    def test_a_failed_subtitle_leg_keeps_the_video(
        self, ready, tmp_path, monkeypatch
    ):
        def fake_video(url, selector, out, **kwargs):
            path = tmp_path / "Video.mp4"
            path.write_bytes(b"v")
            return str(path)

        def fake_sub(url, lang, out, kind="", **kwargs):
            raise RuntimeError("The ja subtitle track could not be downloaded.")

        monkeypatch.setattr(media_source, "download_video", fake_video)
        monkeypatch.setattr(media_source, "download_subtitle", fake_sub)

        ready.download()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert ready.videoOutcome == "ok"
        assert ready.subtitleOutcome == "failed"
        assert ready.history and ready.history[0]["kind"] == "video"

    def test_no_subtitle_selected_downloads_video_only(
        self, ready, tmp_path, monkeypatch
    ):
        calls: list[str] = []
        monkeypatch.setattr(
            media_source, "download_video",
            lambda url, selector, out, **kw: (
                calls.append("video"),
                str((tmp_path / "v.mp4")),
            )[1],
        )
        monkeypatch.setattr(
            media_source, "download_subtitle",
            lambda *a, **k: pytest.fail("no subtitle leg should run"),
        )
        ready.selectedSubtitleTrack = ""

        ready.download()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert calls == ["video"]
        assert ready.videoOutcome == "ok"
        assert ready.subtitleOutcome == "skipped"
        assert ready.downloadProgress == 100

    def test_subtitle_only_does_not_touch_the_video(
        self, ready, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            media_source, "download_video",
            lambda *a, **k: pytest.fail("video leg should not run"),
        )
        monkeypatch.setattr(
            media_source, "download_subtitle",
            lambda url, lang, out, kind="", **kw: str(tmp_path / "s.srt"),
        )
        ready.downloadSubtitleOnly()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert ready.videoOutcome == "skipped"
        assert ready.subtitleOutcome == "ok"


class TestCancel:
    def test_cancel_stops_the_operation_and_reports_it(
        self, ready, tmp_path, monkeypatch
    ):
        started: list[bool] = []

        def slow_video(url, selector, out, **kwargs):
            started.append(True)
            cancel_check = kwargs.get("cancel_check")
            for _ in range(400):
                if cancel_check and cancel_check():
                    raise RuntimeError("Download canceled.")
                time.sleep(0.01)
            raise RuntimeError("timed out")

        monkeypatch.setattr(media_source, "download_video", slow_video)
        monkeypatch.setattr(
            media_source, "download_subtitle",
            lambda *a, **k: pytest.fail("cancel must not start the subtitle leg"),
        )

        ready.download()
        assert _wait(lambda: started), "the video leg never started"
        ready.cancelDownload()
        assert _wait(lambda: not ready.downloadRunning), ready.downloadStatus

        assert ready.videoOutcome == "cancelled"
        assert ready.statusState == "cancelled"
        assert "cancel" in ready.statusMessage.lower()


class TestValidation:
    def test_download_without_a_selection_is_refused(self, bridge, tmp_path):
        _set_url(bridge, "https://example.it/video?v=dQw4w9WgXcQ")
        bridge._download_dir = str(tmp_path)
        bridge.download()
        assert bridge.downloadRunning is False
        assert bridge.downloadError != ""

    def test_download_without_a_url_is_refused(self, bridge):
        bridge.download()
        assert bridge.downloadRunning is False
        assert "URL" in bridge.statusMessage

    def test_unknown_subtitle_code_is_rejected(self, ready):
        ready.selectedSubtitleTrack = "en"
        assert ready.selectedSubtitleTrack == "en"
        ready.selectedSubtitleTrack = "not-a-track"
        assert ready.selectedSubtitleTrack == "en"


class TestSubtitlePreselection:
    def test_original_language_is_selected_by_default(self, bridge, tmp_path):
        bridge._download_dir = str(tmp_path)
        _install(bridge, _payload())
        assert bridge.selectedSubtitleTrack == "ja"
        assert bridge.selectedSubtitleLabel == "Japanese · manual"

    def test_none_mode_preselects_nothing(self, bridge, tmp_path):
        bridge.defaultSubtitleTrack = "none"
        bridge._download_dir = str(tmp_path)
        _install(bridge, _payload())
        assert bridge.selectedSubtitleTrack == ""
        assert bridge.selectedSubtitleLabel == "None — video only"

    def test_first_manual_mode(self, bridge, tmp_path):
        bridge.defaultSubtitleTrack = "manual"
        bridge._download_dir = str(tmp_path)
        _install(bridge, _payload(tracks=[
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": False},
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
        ]))
        assert bridge.selectedSubtitleTrack == "en"

    def test_unknown_original_language_selects_nothing(self, bridge, tmp_path):
        bridge._download_dir = str(tmp_path)
        _install(bridge, _payload(language="fr"))
        assert bridge.selectedSubtitleTrack == ""


class TestSettingsPersistence:
    def test_download_dir_survives_a_restart(self, bridge, tmp_path):
        target = tmp_path / "downloads"
        target.mkdir()
        from PySide6.QtCore import QUrl

        bridge.setDownloadDir(QUrl.fromLocalFile(str(target)))
        bridge.saveSettings()

        from app.bridge import DownloaderBridge

        reopened = DownloaderBridge()
        assert os.path.normpath(reopened.downloadDir) == os.path.normpath(str(target))

    def test_default_subtitle_mode_survives_a_restart(self, bridge):
        bridge.defaultSubtitleTrack = "auto"
        bridge.saveSettings()

        from app.bridge import DownloaderBridge

        assert DownloaderBridge().defaultSubtitleTrack == "auto"

    def test_history_survives_a_restart(self, bridge, tmp_path):
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        bridge._record(str(path), "video")
        assert len(bridge.history) == 1

        from app.bridge import DownloaderBridge

        reopened = DownloaderBridge()
        assert [row["path"] for row in reopened.history] == [str(path)]

    def test_organisation_and_application_are_this_app_only(self):
        assert store.ORGANISATION == "Njoro"
        assert store.APPLICATION == "Saaaveit"


class TestMediaIdentity:
    """T4.1: thumbnail / duration / channel ride along with inspection."""

    def test_properties_follow_the_payload(self, bridge):
        payload = _payload()
        payload.update(
            thumbnail="https://example.com/t.jpg",
            duration=125,
            uploader="Some Channel",
        )
        _install(bridge, payload)
        assert bridge.videoThumbnail == "https://example.com/t.jpg"
        assert bridge.videoDuration == 125
        assert bridge.videoChannel == "Some Channel"

    def test_missing_keys_default_to_empty(self, bridge):
        _install(bridge, _payload())
        assert bridge.videoThumbnail == ""
        assert bridge.videoDuration == 0
        assert bridge.videoChannel == ""

    def test_reset_clears_the_identity(self, bridge):
        payload = _payload()
        payload.update(thumbnail="https://example.com/t.jpg",
                       duration=125, uploader="Some Channel")
        _install(bridge, payload)
        bridge._reset_inspection()
        assert bridge.videoThumbnail == ""
        assert bridge.videoDuration == 0
        assert bridge.videoChannel == ""

    def test_unusable_duration_does_not_abort_inspection(self, bridge):
        """A live stream reports ``Infinity``; the rest of the payload still lands."""
        for bad in (float("inf"), float("nan"), "not-a-number", {"s": 1}):
            payload = _payload()
            payload.update(duration=bad, uploader="Some Channel")
            _install(bridge, payload)
            assert bridge.videoDuration == 0, bad
            assert bridge.videoChannel == "Some Channel", bad
            assert bridge.videoTitle == "Test video", bad


def _wide_payload() -> dict:
    """Two codecs, two heights: enough for a matrix cell to be wrong."""
    codecs, resolutions, matrix, best = media_source._build_matrix([
        {"format_id": "401", "ext": "mp4", "height": 1080,
         "vcodec": "av01.0.13M.10", "acodec": "none", "tbr": 5000,
         "filesize": 40_000_000, "fps": 30},
        {"format_id": "248", "ext": "webm", "height": 720,
         "vcodec": "vp9", "acodec": "none", "tbr": 2000,
         "filesize": 18_000_000, "fps": 30},
        {"format_id": "137", "ext": "mp4", "height": 1080,
         "vcodec": "avc1.640028", "acodec": "none", "tbr": 4500,
         "filesize": 36_000_000, "fps": 30},
        {"format_id": "140", "ext": "m4a", "height": None,
         "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128,
         "filesize": 4_000_000},
    ])
    payload = _payload()
    payload.update(codecs=codecs, resolutions=resolutions, matrix=matrix, best=best)
    return payload


class TestFormatMatrixSelection:
    """``pickFormat``: one cell, both halves, whatever order they arrive in.

    The two setters cannot be driven in sequence from a matrix cell: assigning
    a codec demotes a resolution the new codec does not offer, so the click
    that meant "VP9 at 1080" silently became "VP9 at best" — or, in the other
    order, a selection that does not exist at all.
    """

    @pytest.fixture()
    def wide(self, bridge):
        _set_url(bridge, "https://example.com/video?v=dQw4w9WgXcQ")
        _install(bridge, _wide_payload())
        return bridge

    def test_codec_and_resolution_land_together(self, wide):
        wide.pickFormat("av1", 1080)
        assert wide.selectedCodec == "av1"
        assert wide.selectedResolution == "1080"
        assert wide.selectionError == ""

    def test_int_and_string_forms_of_the_same_cell_agree(self, wide):
        for value in (1080, "1080", 1080.0):
            wide.pickFormat("av1", "best")
            wide.pickFormat("av1", value)
            assert wide.selectedResolution == "1080", value

    def test_a_resolution_the_codec_lacks_falls_back_to_best(self, wide):
        """The matrix would never send this, but a stale binding might."""
        wide.pickFormat("vp9", 1080)
        assert wide.selectedCodec == "vp9"
        assert wide.selectedResolution == "best"
        assert wide.selectionError == ""

    def test_the_best_cell_clears_both_halves(self, wide):
        wide.pickFormat("av1", 720)
        wide.pickFormat("best", "best")
        assert wide.selectedCodec == "best"
        assert wide.selectedResolution == "best"

    def test_picking_the_same_cell_twice_is_not_an_edit(self, wide):
        wide.pickFormat("av1", 1080)
        before = wide.selectedFormatLabel
        wide.pickFormat("av1", 1080)
        assert wide.selectedFormatLabel == before


class TestLibraryRowActions:
    """Remove, launch and open-last: the drawer's buttons, minus the UI."""

    def _seed(self, bridge, tmp_path, names):
        made = []
        for name in names:
            path = tmp_path / name
            path.write_bytes(b"x" * 64)
            bridge._record(str(path), "video")
            made.append(path)
        return made

    def test_remove_drops_the_entry_and_keeps_the_file(self, bridge, tmp_path):
        (kept,) = self._seed(bridge, tmp_path, ["one.mp4"])
        bridge.removeHistory(0)
        assert bridge.historyCount == 0
        assert kept.exists()
        assert "stays on disk" in bridge.statusMessage

    def test_remove_persists_across_a_restart(self, bridge, tmp_path):
        self._seed(bridge, tmp_path, ["one.mp4", "two.mp4"])
        bridge.removeHistory(1)
        store.save_history(bridge._settings, bridge._history)
        assert [os.path.basename(r["path"]) for r in bridge.history] == ["two.mp4"]

    def test_removing_a_row_above_the_selection_follows_the_file(self, bridge, tmp_path):
        self._seed(bridge, tmp_path, ["one.mp4", "two.mp4"])
        # ``_record`` prepends, so the list is [two, one].
        bridge.selectHistory(1)
        bridge.removeHistory(0)
        assert bridge.selectedHistoryIndex == 0
        assert os.path.basename(bridge.history[0]["path"]) == "one.mp4"

    def test_removing_the_selected_row_closes_the_drawer(self, bridge, tmp_path):
        self._seed(bridge, tmp_path, ["one.mp4"])
        bridge.selectHistory(0)
        bridge.removeHistory(0)
        assert bridge.selectedHistoryIndex == -1

    def test_remove_out_of_range_changes_nothing(self, bridge, tmp_path):
        self._seed(bridge, tmp_path, ["one.mp4"])
        bridge.removeHistory(7)
        bridge.removeHistory(-1)
        assert bridge.historyCount == 1

    def test_launch_opens_the_file_itself(self, bridge, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(os, "startfile", opened.append, raising=False)
        self._seed(bridge, tmp_path, ["one.mp4"])
        bridge.launchFile(0)
        assert opened == [str(tmp_path / "one.mp4")]

    def test_launching_a_missing_file_says_so(self, bridge, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(os, "startfile", opened.append, raising=False)
        self._seed(bridge, tmp_path, ["one.mp4"])
        (tmp_path / "one.mp4").unlink()
        bridge.launchFile(0)
        assert opened == []
        assert "missing from disk" in bridge.statusMessage

    def test_open_last_file_uses_the_newest_entry(self, bridge, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(os, "startfile", opened.append, raising=False)
        self._seed(bridge, tmp_path, ["one.mp4", "two.mp4"])
        bridge.openLastFile()
        # ``_record`` prepends, so the newest row is also the last file written.
        assert opened == [str(tmp_path / "two.mp4")]

    def test_open_last_file_on_an_empty_library(self, bridge):
        bridge.openLastFile()
        assert bridge.statusMessage == "Nothing downloaded yet."


class TestCopyAndPreview:
    def test_copy_video_id_reaches_the_clipboard(self, bridge, gui_app):
        from PySide6.QtGui import QGuiApplication

        _install(bridge, _payload())
        bridge.copyVideoId()
        assert QGuiApplication.clipboard().text() == "dQw4w9WgXcQ"
        assert bridge.statusMessage == "Video ID copied."

    def test_copy_video_id_without_a_video_is_a_no_op(self, bridge, gui_app):
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText("untouched")
        bridge.copyVideoId()
        assert QGuiApplication.clipboard().text() == "untouched"

    def test_preview_fills_known_fields_and_appends_the_extension(self, bridge):
        assert bridge.filenamePreview == "How Compilers Turn Code into Machines [c0mP1l3r].mp4"

    def test_preview_leaves_an_unknown_field_literal(self, bridge):
        """A typo must not preview as a filename that will never appear."""
        bridge.filenameTemplate = "%(title)s-%(uploader)s"
        assert bridge.filenamePreview == "How Compilers Turn Code into Machines-%(uploader)s.mp4"

    def test_preview_does_not_double_an_explicit_extension(self, bridge):
        bridge.filenameTemplate = "%(id)s.%(ext)s"
        assert bridge.filenamePreview == "c0mP1l3r.mp4"

    def test_an_empty_template_falls_back_to_the_default(self, bridge):
        bridge.filenameTemplate = ""
        assert bridge.filenameTemplate == store.DEFAULT_FILENAME_TEMPLATE
        assert bridge.filenamePreview.endswith(".mp4")


class TestShortcutBinding:
    def test_rows_report_which_ones_are_still_default(self, bridge):
        assert bridge.setShortcut("palette", "Ctrl+Shift+P") == ""
        rows = {row["action"]: row for row in bridge.shortcutRows}
        assert rows["palette"]["isDefault"] is False
        assert rows["inspect"]["isDefault"] is True

    def test_a_bare_key_is_refused(self, bridge):
        assert "Ctrl or Alt" in bridge.setShortcut("palette", "P")
        assert bridge.shortcutFor("palette") == "Ctrl+K"

    def test_a_collision_names_the_other_action(self, bridge):
        message = bridge.setShortcut("palette", "Ctrl+1")
        assert "Ctrl+1" in message and "Go to Download" in message

    def test_restoring_a_default_can_itself_collide(self, bridge):
        # Two rows swapped: putting either one back lands on the other's chord.
        assert bridge.setShortcut("goto_download", "Ctrl+9") == ""
        assert bridge.setShortcut("palette", "Ctrl+1") == ""
        message = bridge.resetShortcut("goto_download")
        assert "Ctrl+1" in message and "Command palette" in message
        assert bridge.shortcutFor("goto_download") == "Ctrl+9"

    def test_reset_all_shortcuts_returns_every_row(self, bridge):
        assert bridge.setShortcut("cancel", "Ctrl+J") == ""
        bridge.resetAllShortcuts()
        assert all(row["isDefault"] for row in bridge.shortcutRows)


class TestEnvironmentRows:
    def test_rows_carry_ids_so_a_page_can_pick_its_own_three(self, bridge):
        rows = bridge.environmentRows
        by_id = {row["id"]: row["label"] for row in rows}
        assert {"settings_store", "log_file", "python"} <= set(by_id)
        assert by_id["python"] == "Python"


class TestRedownload:
    """The drawer's Redownload: hand the URL to Download, then run what was
    recorded once the inspection lands - and never run it twice."""

    def _seed(self, bridge, tmp_path, kind="video"):
        path = tmp_path / ("clip [dQw4w9WgXcQ].mp4" if kind == "video"
                           else "clip [dQw4w9WgXcQ].en.srt")
        path.write_bytes(b"x" * 64)
        _set_url(bridge, "https://example.com/video?v=dQw4w9WgXcQ")
        _install(bridge, _payload())
        if kind == "subtitle":
            # Record with an explicit English track, so ``detail`` is a label
            # the tests below can remove again on purpose.
            bridge.selectedSubtitleTrack = "en"
        bridge._record(str(path), kind)
        return bridge

    def test_redownload_navigates_and_arms_the_pending_run(self, bridge, tmp_path, monkeypatch):
        self._seed(bridge, tmp_path)
        inspected = []
        monkeypatch.setattr(bridge, "inspect", lambda: inspected.append("inspect"))
        tabs = []
        bridge.requestTab.connect(tabs.append)
        bridge.redownload(0)
        assert tabs == [0]
        assert inspected == ["inspect"]
        assert bridge._pending_redownload["kind"] == "video"
        # The recorded format label rides along; the video run ignores it.
        assert bridge._pending_redownload["detail"]

    def test_the_landing_inspection_starts_exactly_one_run(self, bridge, tmp_path, monkeypatch):
        self._seed(bridge, tmp_path)
        monkeypatch.setattr(bridge, "inspect", lambda: None)
        runs = []
        monkeypatch.setattr(bridge, "download", lambda: runs.append("download"))
        bridge.redownload(0)
        _install(bridge, _payload())
        assert runs == ["download"]
        assert bridge._pending_redownload is None
        # A second inspection of the same video must not start a second run.
        _install(bridge, _payload())
        assert runs == ["download"]

    def test_a_subtitle_entry_reselects_and_runs_its_track(self, bridge, tmp_path, monkeypatch):
        self._seed(bridge, tmp_path, kind="subtitle")
        monkeypatch.setattr(bridge, "inspect", lambda: None)
        subs = []
        monkeypatch.setattr(bridge, "downloadSubtitleOnly", lambda: subs.append("sub"))
        bridge.redownload(0)
        _install(bridge, _payload())
        assert subs == ["sub"]
        assert bridge.selectedSubtitleTrack == "en"

    def test_a_subtitle_track_that_no_longer_exists_only_says_so(self, bridge, tmp_path, monkeypatch):
        self._seed(bridge, tmp_path, kind="subtitle")
        monkeypatch.setattr(bridge, "inspect", lambda: None)
        subs = []
        monkeypatch.setattr(bridge, "downloadSubtitleOnly", lambda: subs.append("sub"))
        bridge.redownload(0)
        # The new inspection offers no English track any more.
        _install(bridge, _payload(tracks=[
            {"code": "ja", "name": "Japanese", "kind": "manual",
             "label": "Japanese · manual", "isOriginal": True},
        ]))
        assert subs == []
        assert "no longer offered" in bridge.statusMessage

    def test_a_failed_inspection_drops_the_pending_run(self, bridge, tmp_path, monkeypatch):
        self._seed(bridge, tmp_path)
        monkeypatch.setattr(bridge, "inspect", lambda: None)
        runs = []
        monkeypatch.setattr(bridge, "download", lambda: runs.append("download"))
        bridge.redownload(0)
        bridge._info_gen += 1
        bridge._on_info_done(f"INFOERROR:{bridge._info_gen}|Could not reach the page")
        assert bridge._pending_redownload is None
        assert runs == []

    def test_redownload_is_refused_while_a_download_runs(self, bridge, tmp_path):
        self._seed(bridge, tmp_path)
        bridge._download_running = True
        tabs = []
        bridge.requestTab.connect(tabs.append)
        bridge.redownload(0)
        assert tabs == []
        assert bridge._pending_redownload is None
        assert "running download" in bridge.statusMessage
        bridge._download_running = False

    def test_an_entry_without_a_source_url_says_so(self, bridge, tmp_path):
        path = tmp_path / "clip [dQw4w9WgXcQ].mp4"
        path.write_bytes(b"x" * 64)
        bridge._history = [{"path": str(path), "kind": "video", "detail": "VP9 · 1080p"}]
        bridge.historyChanged.emit()
        bridge.redownload(0)
        assert bridge._pending_redownload is None
        assert "without a source URL" in bridge.statusMessage
