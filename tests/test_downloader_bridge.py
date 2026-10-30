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


@pytest.fixture()
def ready(bridge, tmp_path, monkeypatch):
    """A bridge with a URL, an inspected video and a writable temp output dir."""
    bridge.url = "https://example.com/video?v=dQw4w9WgXcQ"
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
        bridge.url = "https://example.it/video?v=dQw4w9WgXcQ"
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
