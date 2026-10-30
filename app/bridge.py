"""The QML bridge for the Saaaveit downloader.

One object, exposed to QML as ``appBridge``. It owns:

  * inspection state (formats + subtitle tracks for the current URL),
  * the single download operation (video leg, then the selected subtitle leg),
  * the persisted library of downloaded files,
  * the persisted appearance/settings, the log and the status line.

There is no translation anything in here: this app downloads files.
"""
from __future__ import annotations

import logging
import logging.handlers
import json
import os
import re
import sys

from PySide6.QtCore import (
    Property,
    QObject,
    QSettings,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from src import store, media_source
from src.store import DEFAULT_FILENAME_TEMPLATE
from src.ytdlp import yt_dlp_available

from .workers import DownloadWorker, InfoWorker
from .thumbnail import cached_thumbnail

APP_NAME = "Saaaveit"
APP_VERSION = "1.0.0"

STATUS_READY = "ready"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

READINESS_OK = "ok"
READINESS_TODO = "todo"
READINESS_NA = "na"

_LOG_ERROR_RE = re.compile(r"^\[error\]|^\s*(?:ERROR|error)\s*:", re.IGNORECASE)
_LOG_WARN_RE = re.compile(r"^\[warn(ing)?\]|^\s*(?:WARNING|warn)\s*:", re.IGNORECASE)

_SHORTCUT_DEFAULTS = {
    "goto_download": "Ctrl+1",
    "goto_library": "Ctrl+2",
    "goto_settings": "Ctrl+,",
    "palette": "Ctrl+K",
    "download": "Ctrl+Return",
    "download_subtitle": "Ctrl+Shift+Return",
    "inspect": "Ctrl+I",
    "cancel": "Ctrl+.",
    "open_folder": "Ctrl+O",
    "open_last": "Ctrl+S",
}

_SHORTCUT_LABELS = {
    "goto_download": "Go to Download",
    "goto_library": "Go to Library",
    "goto_settings": "Go to Settings",
    "palette": "Command palette",
    "download": "Download",
    "download_subtitle": "Fetch subtitle only",
    "inspect": "Inspect formats",
    "cancel": "Cancel download",
    "open_folder": "Open download folder",
    "open_last": "Open last downloaded file",
}


def _is_writable_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    probe = os.path.join(path, f".write-probe-{os.getpid()}")
    try:
        with open(probe, "w", encoding="utf-8"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def base_dir() -> str:
    """The folder this app lives in (next to the .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logging(base: str) -> logging.Logger:
    logger = logging.getLogger("saaaveit")
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    path = os.path.join(base, "saaaveit.log")
    if not _is_writable_dir(base):
        path = os.path.join(store.app_data_dir(), "saaaveit.log")
    try:
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        return logger
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    return logger


def format_bytes(num) -> str:
    try:
        value = float(num or 0)
    except (TypeError, ValueError):
        return "—"
    if value <= 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}PB"


class DownloaderBridge(QObject):
    formChanged = Signal()
    statusMessageChanged = Signal()
    statusStateChanged = Signal()
    logTextChanged = Signal()
    logCountsChanged = Signal()
    inspectChanged = Signal()
    downloadChanged = Signal()
    canDownloadChanged = Signal()
    historyChanged = Signal()
    themeChanged = Signal()
    readinessChanged = Signal()
    failureChanged = Signal()
    savedToast = Signal()
    dirtyChanged = Signal()
    shortcutsChanged = Signal()
    requestTab = Signal(int)

    _PERSISTED = (
        ("_download_dir", "downloads/dir", ""),
        ("_default_subtitle_track", "downloads/subtitleTrack", "original"),
        ("_filename_template", "downloads/filenameTemplate", DEFAULT_FILENAME_TEMPLATE),
        ("_theme_name", "ui/theme", "dark"),
        ("_accent_name", "ui/accent", "iris"),
        ("_comfortable", "ui/comfortable", False),
        ("_reduced_motion", "ui/reducedMotion", False),
        ("_shortcuts_json", "ui/shortcuts", "{}"),
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.threadpool = QThreadPool()
        self.logger = logging.getLogger("saaaveit")
        self._settings: QSettings = store.settings()

        # --- source / inspection ------------------------------------------
        self._url = ""
        self._info_loading = False
        self._info_error = ""
        self._title = ""
        self._video_id = ""
        self._language = ""
        self._thumbnail = ""
        self._duration = 0
        self._uploader = ""
        self._codecs: list[str] = []
        self._resolutions: list[int] = []
        self._matrix: dict = {}
        self._best: dict = {}
        self._codecs_available = {"av1": False, "vp9": False, "h264": False}
        self._subtitle_tracks: list[dict] = []
        self._selected_codec = "best"
        self._selected_resolution = "best"
        self._selected_subtitle = ""
        self._info_worker: InfoWorker | None = None
        self._info_gen = 0

        # --- the download operation ---------------------------------------
        self._op_gen = 0
        self._video_worker: DownloadWorker | None = None
        self._sub_worker: DownloadWorker | None = None
        self._download_running = False
        self._progress = 0
        self._stage = ""
        self._download_status = ""
        self._download_notice = ""
        self._download_error = ""
        self._video_outcome = ""
        self._subtitle_outcome = ""
        self._downloaded_video = ""
        self._downloaded_subtitle = ""
        self._pending: list[str] = []
        self._subtitle_leg_wanted = False
        self._cancel_requested = False

        # --- settings / chrome -------------------------------------------
        self._download_dir = ""
        self._default_subtitle_track = "original"
        self._filename_template = DEFAULT_FILENAME_TEMPLATE
        self._theme_name = "dark"
        self._accent_name = "iris"
        self._comfortable = False
        self._reduced_motion = False
        self._shortcuts_json = "{}"
        self._history: list[dict] = []
        self._selected_history = -1

        self._status_message = "Ready."
        self._status_state = STATUS_READY
        self._log_text = ""
        self._log_error_count = 0
        self._log_warn_count = 0

        self._failure_code = ""
        self._failure_title = ""
        self._failure_detail = ""
        self._failure_remediation = ""

        self._win_x, self._win_y, self._win_w, self._win_h = 80, 60, 1240, 820

        self._dirty = False
        self._loading = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._commit_pending)

        self._load_persisted()

        # `canDownload` depends on both the inspected formats and the download
        # state, so it must be re-evaluated when either changes.
        self.inspectChanged.connect(self.canDownloadChanged)
        self.downloadChanged.connect(self.canDownloadChanged)

    # ---------------------------------------------------------------- store
    def _load_persisted(self) -> None:
        self._loading = True
        try:
            for attr, key, default in self._PERSISTED:
                value = self._settings.value(key, default)
                if isinstance(default, bool):
                    setattr(self, attr, str(value).lower() in ("1", "true", "yes"))
                elif isinstance(default, str):
                    setattr(self, attr, value if isinstance(value, str) else default)
            self._history = store.load_history(self._settings)
            for key, attr, cast in (
                ("window/x", "_win_x", int),
                ("window/y", "_win_y", int),
                ("window/w", "_win_w", int),
                ("window/h", "_win_h", int),
            ):
                try:
                    setattr(self, attr, cast(self._settings.value(key, getattr(self, attr))))
                except (TypeError, ValueError):
                    pass
            self._notify_form_changed()
        finally:
            self._loading = False

    def _persist_fields(self) -> None:
        for attr, key, _default in self._PERSISTED:
            self._settings.setValue(key, getattr(self, attr, ""))
        for key, attr in (
            ("window/x", "_win_x"),
            ("window/y", "_win_y"),
            ("window/w", "_win_w"),
            ("window/h", "_win_h"),
        ):
            self._settings.setValue(key, getattr(self, attr))
        store.save_history(self._settings, self._history)
        self._settings.sync()

    def _notify_form_changed(self) -> None:
        self.formChanged.emit()
        self.readinessChanged.emit()
        if not self._loading:
            if not self._dirty:
                self._dirty = True
                self.dirtyChanged.emit()
            self._save_timer.start()

    def _set_field(self, attr: str, value) -> None:
        if getattr(self, attr) != value:
            setattr(self, attr, value)
            self._notify_form_changed()

    def _commit_pending(self) -> None:
        if not self._dirty:
            return
        self._persist_fields()
        self._dirty = False
        self.dirtyChanged.emit()
        self.savedToast.emit()

    @Slot()
    def saveSettings(self) -> None:
        self._persist_fields()
        self._dirty = False
        self.dirtyChanged.emit()

    @Property(bool, notify=dirtyChanged)
    def dirty(self) -> bool:
        return self._dirty

    # ---------------------------------------------------------------- log
    def _append_log(self, text: str) -> None:
        self._log_text += text
        errors = warnings = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _LOG_ERROR_RE.search(line):
                errors += 1
            elif _LOG_WARN_RE.search(line):
                warnings += 1
            self.logger.info(line)
        if errors or warnings:
            self._log_error_count += errors
            self._log_warn_count += warnings
            self.logCountsChanged.emit()
        if len(self._log_text) > 400_000:
            self._log_text = self._log_text[-200_000:]
        self.logTextChanged.emit()

    @Property(str, notify=logTextChanged)
    def logText(self) -> str:
        return self._log_text

    @Property(int, notify=logCountsChanged)
    def logErrorCount(self) -> int:
        return self._log_error_count

    @Property(int, notify=logCountsChanged)
    def logWarnCount(self) -> int:
        return self._log_warn_count

    @Slot()
    def clearLog(self) -> None:
        self._log_text = ""
        self._log_error_count = 0
        self._log_warn_count = 0
        self.logTextChanged.emit()
        self.logCountsChanged.emit()

    @Slot()
    def copyLog(self) -> None:
        QGuiApplication.clipboard().setText(self._log_text)

    @Slot()
    def exportLog(self) -> None:
        path = os.path.join(base_dir(), "saaaveit-log.txt")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._log_text)
            self._set_status(f"Log exported to {path}")
        except OSError as exc:
            self._set_status(f"Could not export the log: {exc}")

    @Slot()
    def openDebugLog(self) -> None:
        self.openFolderForPath(os.path.join(base_dir(), "saaaveit.log"))

    # ------------------------------------------------------------- status
    def _set_status(self, text: str) -> None:
        self._status_message = text or ""
        self.statusMessageChanged.emit()

    def _set_status_state(self, state: str) -> None:
        if self._status_state != state:
            self._status_state = state
            self.statusStateChanged.emit()

    @Slot(str)
    def setStatusMessage(self, text: str) -> None:
        self._set_status(text)

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusStateChanged)
    def statusState(self) -> str:
        return self._status_state

    # ------------------------------------------------------------- source
    @Property(str, notify=formChanged)
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        value = (value or "").strip()
        if value == self._url:
            return
        self._url = value
        # A new URL invalidates everything we learned about the old one, and any
        # download in flight belongs to the old one too.
        self._reset_inspection()
        if value:
            self.inspect()
        self._notify_form_changed()

    @Slot()
    def clearSource(self) -> None:
        self.url = ""

    def _reset_inspection(self) -> None:
        self._info_error = ""
        self._title = ""
        self._video_id = ""
        self._language = ""
        self._thumbnail = ""
        self._duration = 0
        self._uploader = ""
        self._codecs = []
        self._resolutions = []
        self._matrix = {}
        self._best = {}
        self._codecs_available = {"av1": False, "vp9": False, "h264": False}
        self._subtitle_tracks = []
        self._selected_codec = "best"
        self._selected_resolution = "best"
        self._selected_subtitle = ""
        self.inspectChanged.emit()

    # --------------------------------------------------------- inspection
    @Slot()
    def inspect(self) -> None:
        url = self._url.strip()
        if not url:
            self._info_error = "Paste a video URL first."
            self.inspectChanged.emit()
            return
        if self._info_loading or self._download_running:
            return
        self._info_loading = True
        self._info_error = ""
        self._matrix = {}
        self._best = {}
        self._codecs = []
        self._resolutions = []
        self._subtitle_tracks = []
        self._selected_codec = "best"
        self._selected_resolution = "best"
        self._selected_subtitle = ""
        self.inspectChanged.emit()
        self._set_status("Inspecting formats and subtitle tracks…")
        self._set_status_state(STATUS_RUNNING)

        self._info_gen += 1
        worker = InfoWorker(url, self._info_gen)
        worker.signals.done.connect(self._on_info_done)
        self._info_worker = worker
        self.threadpool.start(worker)

    def _on_info_done(self, payload: str) -> None:
        token = self._payload_token(payload)
        if token != self._info_gen:
            return
        self._info_worker = None
        self._info_loading = False
        if payload.startswith("INFOERROR:"):
            self._info_error = payload.split("|", 1)[-1].strip()
            self.inspectChanged.emit()
            self._set_status(self._info_error)
            self._set_status_state(STATUS_FAILED)
            return
        try:
            info = json.loads(payload.split("|", 1)[-1])
        except (ValueError, TypeError):
            self._info_error = "Could not parse the inspection result."
            self.inspectChanged.emit()
            self._set_status(self._info_error)
            self._set_status_state(STATUS_FAILED)
            return

        self._title = info.get("title") or ""
        self._video_id = info.get("video_id") or ""
        self._language = info.get("language") or ""
        self._thumbnail = str(info.get("thumbnail") or "")
        try:
            self._duration = int(info.get("duration") or 0)
        except (TypeError, ValueError):
            self._duration = 0
        self._uploader = str(info.get("uploader") or info.get("channel") or "")
        self._matrix = {
            cid: {int(h): opt for h, opt in (family or {}).items()}
            for cid, family in (info.get("matrix") or {}).items()
        }
        self._best = info.get("best") or {}
        self._codecs = info.get("codecs") or []
        self._resolutions = info.get("resolutions") or []
        available = info.get("codecs_available") or {}
        self._codecs_available = {
            "av1": bool(available.get("av1")),
            "vp9": bool(available.get("vp9")),
            "h264": bool(available.get("h264")),
        }
        self._subtitle_tracks = info.get("subtitle_tracks") or []
        self._selected_codec = self._codecs[0] if self._codecs else "best"
        self._selected_resolution = "best"
        self._selected_subtitle = self._default_track_for(info)
        self.inspectChanged.emit()
        self._set_status(
            f"Inspected “{self._title}” — {len(self._codecs)} codec(s), "
            f"{len(self._resolutions)} resolution(s), "
            f"{len(self._subtitle_tracks)} subtitle track(s)."
        )
        self._set_status_state(STATUS_READY)

    def _default_track_for(self, info: dict) -> str:
        mode = (self._default_subtitle_track or "original").strip().lower()
        tracks = info.get("subtitle_tracks") or []
        if mode == "none":
            return ""
        if mode == "original":
            return str(info.get("default_subtitle_track") or "")
        for track in tracks:
            if track.get("kind") == mode:
                return str(track.get("code") or "")
        return ""

    @staticmethod
    def _payload_token(payload: str) -> int:
        try:
            return int(payload.split("|", 1)[0].rsplit(":", 1)[1])
        except (IndexError, ValueError):
            return -1

    @Property(bool, notify=inspectChanged)
    def infoLoading(self) -> bool:
        return self._info_loading

    @Property(str, notify=inspectChanged)
    def infoError(self) -> str:
        return self._info_error

    @Property(bool, notify=inspectChanged)
    def hasInfo(self) -> bool:
        return bool(self._codecs or self._matrix or self._best)

    @Property(str, notify=inspectChanged)
    def videoTitle(self) -> str:
        return self._title

    @Property(str, notify=inspectChanged)
    def videoId(self) -> str:
        return self._video_id

    @Property(str, notify=inspectChanged)
    def videoThumbnail(self) -> str:
        return self._thumbnail

    @Property(int, notify=inspectChanged)
    def videoDuration(self) -> int:
        return self._duration

    @Property(str, notify=inspectChanged)
    def videoChannel(self) -> str:
        return self._uploader

    @Property(str, notify=inspectChanged)
    def sourceLanguage(self) -> str:
        return self._language

    @Property(list, notify=inspectChanged)
    def codecs(self) -> list:
        items = [
            {"id": cid, "label": media_source._CODEC_LABEL.get(cid, str(cid).upper())}
            for cid in self._codecs
        ]
        items.append({"id": "best", "label": "Best (any)"})
        return items

    @Property(list, notify=inspectChanged)
    def resolutions(self) -> list:
        selected = (self._selected_codec or "best").strip() or "best"
        family = (self._matrix or {}).get(selected) if selected != "best" else None
        if family:
            heights = sorted((int(h) for h in family), reverse=True)
        else:
            heights = sorted((int(h) for h in self._resolutions), reverse=True)
        items = [{"value": str(h), "label": f"{h}p"} for h in heights]
        items.append({"value": "best", "label": "Best"})
        return items

    @Property(bool, notify=inspectChanged)
    def hasAv1(self) -> bool:
        return self._codecs_available.get("av1", False)

    @Property(bool, notify=inspectChanged)
    def hasVp9(self) -> bool:
        return self._codecs_available.get("vp9", False)

    @Property(bool, notify=inspectChanged)
    def hasH264(self) -> bool:
        return self._codecs_available.get("h264", False)

    @Property(list, notify=inspectChanged)
    def formatRows(self) -> list:
        if not self._matrix and not self._best:
            return []
        order = {cid: i for i, cid in enumerate(media_source._CODEC_ORDER)}
        selected_codec = (self._selected_codec or "best").strip() or "best"
        selected_res = self._selected_resolution
        max_height = {
            cid: max(family) for cid, family in self._matrix.items() if family
        }
        rows: list[dict] = []
        for cid, family in self._matrix.items():
            for height, option in family.items():
                size = int(option.get("filesize") or 0)
                fps = int(option.get("fps") or 0)
                merge = bool(option.get("merge"))
                bits = [option.get("ext") or ""]
                if fps:
                    bits.append(f"{fps}fps")
                text = " · ".join(b for b in bits if b)
                if merge:
                    text = (text + " · " if text else "") + "video+audio merge"
                elif not text:
                    text = "—"
                selected = selected_codec == cid and (
                    height == max_height.get(cid)
                    if selected_res == "best"
                    else str(height) == str(selected_res)
                )
                rows.append({
                    "isBest": False,
                    "selected": selected,
                    "codec": cid,
                    "codecLabel": media_source._CODEC_LABEL.get(cid, str(cid).upper()),
                    "resolution": int(height),
                    "resLabel": f"{int(height)}p",
                    "formatText": text,
                    "sizeText": format_bytes(size) if size else "—",
                    "merge": merge,
                })
        if self._best:
            rows.append({
                "isBest": True,
                "selected": selected_codec == "best",
                "codec": "best",
                "codecLabel": "Best (any)",
                "resolution": "best",
                "resLabel": "Best",
                "formatText": "auto",
                "sizeText": "—",
                "merge": False,
            })
        rows.sort(key=lambda row: (
            0 if row["isBest"] else 1,
            -int(row["resolution"]) if not row["isBest"] else 0,
            order.get(row["codec"], 99),
        ))
        return rows

    @Property(str, notify=inspectChanged)
    def selectedCodec(self) -> str:
        return self._selected_codec

    @selectedCodec.setter
    def selectedCodec(self, value: str) -> None:
        value = (value or "best").strip() or "best"
        if value == self._selected_codec:
            return
        self._selected_codec = value
        family = self._matrix.get(value) if value != "best" else None
        if family and self._selected_resolution != "best":
            if str(self._selected_resolution) not in {str(h) for h in family}:
                self._selected_resolution = "best"
        self.inspectChanged.emit()

    @Property(str, notify=inspectChanged)
    def selectedResolution(self) -> str:
        return self._selected_resolution

    @selectedResolution.setter
    def selectedResolution(self, value) -> None:
        value = media_source.normalize_resolution(value)
        if value != self._selected_resolution:
            self._selected_resolution = value
            self.inspectChanged.emit()

    @Property(str, notify=inspectChanged)
    def selectionError(self) -> str:
        if not self._matrix and not self._best:
            return ""
        return media_source.describe_unavailable(
            {"matrix": self._matrix, "best": self._best},
            self._selected_codec,
            self._selected_resolution,
        )

    @Property(dict, notify=inspectChanged)
    def selectedOption(self) -> dict:
        if not self._matrix and not self._best:
            return {}
        return media_source.resolve_video_option(
            {"matrix": self._matrix, "best": self._best},
            self._selected_codec,
            self._selected_resolution,
        ) or {}

    @Property(int, notify=inspectChanged)
    def selectedFileSize(self) -> int:
        return int((self.selectedOption or {}).get("filesize") or 0)

    @Property(str, notify=inspectChanged)
    def selectedFormatLabel(self) -> str:
        return (self.selectedOption or {}).get("label") or ""

    @Property(str, notify=inspectChanged)
    def selectedFileSizeText(self) -> str:
        size = self.selectedFileSize
        return format_bytes(size) if size else "unknown until download"

    # ------------------------------------------------------ subtitle tracks
    @Property(list, notify=inspectChanged)
    def subtitleTracks(self) -> list:
        return list(self._subtitle_tracks)

    @Property(bool, notify=inspectChanged)
    def hasSubtitleTracks(self) -> bool:
        return bool(self._subtitle_tracks)

    @Property(str, notify=inspectChanged)
    def selectedSubtitleTrack(self) -> str:
        return self._selected_subtitle

    @selectedSubtitleTrack.setter
    def selectedSubtitleTrack(self, value: str) -> None:
        value = (value or "").strip()
        known = {str(t.get("code") or "") for t in self._subtitle_tracks}
        if value and value not in known:
            return
        if value != self._selected_subtitle:
            self._selected_subtitle = value
            self.inspectChanged.emit()

    def _selected_subtitle_kind(self) -> str:
        for track in self._subtitle_tracks:
            if str(track.get("code") or "") == self._selected_subtitle:
                return str(track.get("kind") or "")
        return ""

    @Property(str, notify=inspectChanged)
    def selectedSubtitleLabel(self) -> str:
        if not self._selected_subtitle:
            return "None — video only"
        for track in self._subtitle_tracks:
            if str(track.get("code") or "") == self._selected_subtitle:
                return str(track.get("label") or self._selected_subtitle)
        return self._selected_subtitle

    # ---------------------------------------------------- download settings
    @Property(str, notify=formChanged)
    def downloadDir(self) -> str:
        custom = (self._download_dir or "").strip()
        if custom:
            return custom
        videos = os.path.join(os.path.expanduser("~"), "Videos")
        return videos if os.path.isdir(videos) else os.path.expanduser("~")

    @Slot(QUrl)
    def setDownloadDir(self, url: QUrl) -> None:
        path = url.toLocalFile() if url.isValid() else ""
        if not path or path == self._download_dir:
            return
        self._download_dir = path
        self._set_status(f"Downloads will be saved to: {path}")
        self._notify_form_changed()

    @Property(str, notify=formChanged)
    def defaultSubtitleTrack(self) -> str:
        return self._default_subtitle_track

    @defaultSubtitleTrack.setter
    def defaultSubtitleTrack(self, value: str) -> None:
        self._set_field("_default_subtitle_track", (value or "original").strip())

    @Property(list, notify=formChanged)
    def defaultSubtitleChoices(self) -> list:
        return [
            {"id": "original", "label": "Original language (recommended)"},
            {"id": "manual", "label": "First manual track"},
            {"id": "auto", "label": "First auto-generated track"},
            {"id": "none", "label": "None — never preselect"},
        ]

    @Property(str, notify=formChanged)
    def filenameTemplate(self) -> str:
        return self._filename_template

    @filenameTemplate.setter
    def filenameTemplate(self, value: str) -> None:
        self._set_field("_filename_template", (value or "").strip() or DEFAULT_FILENAME_TEMPLATE)

    def _out_template(self) -> str:
        return os.path.join(self.downloadDir, self._filename_template)

    # ------------------------------------------------------------ download
    @Property(bool, notify=downloadChanged)
    def downloadRunning(self) -> bool:
        return self._download_running

    @Property(int, notify=downloadChanged)
    def downloadProgress(self) -> int:
        return self._progress

    @Property(str, notify=downloadChanged)
    def downloadStage(self) -> str:
        return self._stage

    @Property(str, notify=downloadChanged)
    def downloadStatus(self) -> str:
        return self._download_status

    @Property(str, notify=downloadChanged)
    def downloadNotice(self) -> str:
        return self._download_notice

    @Property(str, notify=downloadChanged)
    def downloadError(self) -> str:
        return self._download_error

    @Property(str, notify=downloadChanged)
    def videoOutcome(self) -> str:
        return self._video_outcome

    @Property(str, notify=downloadChanged)
    def subtitleOutcome(self) -> str:
        return self._subtitle_outcome

    @Property(str, notify=downloadChanged)
    def downloadedVideo(self) -> str:
        return self._downloaded_video

    @Property(str, notify=downloadChanged)
    def downloadedSubtitle(self) -> str:
        return self._downloaded_subtitle

    @Property(bool, notify=canDownloadChanged)
    def canDownload(self) -> bool:
        return bool(self.hasInfo and self.url and not self._download_running
                    and bool(self.selectedOption.get("format_selector")))

    def _selector(self) -> str:
        return str((self.selectedOption or {}).get("format_selector") or "")

    def _expectation(self) -> dict:
        option = self.selectedOption or {}
        try:
            height = int(option.get("resolution") or 0)
        except (TypeError, ValueError):
            height = 0
        codec = str(option.get("codec") or "").strip().lower()
        return {"codec": codec, "height": height, "cap": codec == "best"}

    @Slot()
    def download(self) -> None:
        """Download the selected video format and, if one is selected, a subtitle."""
        if not self._begin_operation(include_subtitle=True):
            return
        self._start_video_leg()

    @Slot()
    def downloadSubtitleOnly(self) -> None:
        """Download just the selected subtitle track (the video is already on disk)."""
        if not self._selected_subtitle:
            self._set_status("Select a subtitle track first.")
            return
        if not self._begin_operation(include_subtitle=True, video=False):
            return
        self._start_subtitle_leg()

    def _begin_operation(self, *, include_subtitle: bool, video: bool = True) -> bool:
        if self._download_running:
            return False
        if not self.url:
            self._set_status("Paste a video URL first.")
            return False
        if video:
            selector = self._selector()
            if not selector:
                reason = self.selectionError or (
                    "This video is not available in the selected format."
                )
                self._download_notice = reason
                self._download_error = reason
                self._download_status = f"[error] {reason}\n"
                self.downloadChanged.emit()
                self._set_status(reason)
                self._set_status_state(STATUS_FAILED)
                return False
        if include_subtitle and not self._selected_subtitle and not video:
            return False

        self._op_gen += 1
        self._cancel_requested = False
        self._download_running = True
        self._progress = 0
        self._stage = "preparing"
        self._download_status = ""
        self._download_notice = ""
        self._download_error = ""
        self._video_outcome = "" if video else "skipped"
        self._subtitle_outcome = "" if (include_subtitle and self._selected_subtitle) else "skipped"
        self._downloaded_video = ""
        self._downloaded_subtitle = ""
        self._subtitle_leg_wanted = bool(include_subtitle and self._selected_subtitle)
        self._pending = []
        self.downloadChanged.emit()
        self._set_status_state(STATUS_RUNNING)
        return True

    def _start_video_leg(self) -> None:
        self._pending.append("video")
        self._stage = "video"
        self._download_status += "Preparing video download…\n"
        self.downloadChanged.emit()
        worker = DownloadWorker(
            "video",
            self.url,
            format_selector=self._selector(),
            out_template=self._out_template() + ".%(ext)s",
            token=self._op_gen,
            expect=self._expectation(),
        )
        worker.signals.progress.connect(self._append_log)
        worker.signals.progress.connect(self._on_download_line)
        worker.signals.percent.connect(self._on_video_percent)
        worker.signals.done.connect(self._on_leg_done)
        self._video_worker = worker
        self.threadpool.start(worker)

    def _start_subtitle_leg(self) -> None:
        self._pending.append("subtitle")
        self._stage = "subtitle"
        self._progress = max(self._progress, 85)
        self._download_status += (
            f"Fetching the {self._selected_subtitle} subtitle track…\n"
        )
        self.downloadChanged.emit()
        worker = DownloadWorker(
            "subtitle",
            self.url,
            out_template=self._out_template(),
            token=self._op_gen,
            subtitle_lang=self._selected_subtitle,
            subtitle_kind=self._selected_subtitle_kind(),
        )
        worker.signals.progress.connect(self._append_log)
        worker.signals.progress.connect(self._on_download_line)
        worker.signals.done.connect(self._on_leg_done)
        self._sub_worker = worker
        self.threadpool.start(worker)

    def _on_download_line(self, text: str) -> None:
        self._download_status += text
        if text.lstrip().startswith("[warn]"):
            notice = text.strip()[len("[warn]"):].strip()
            if notice:
                self._download_notice = notice
        lowered = text.lower()
        if "[audio]" in lowered:
            self._stage = "audio"
        elif "merging formats into" in lowered or lowered.startswith("[merger]"):
            self._stage = "merging"
        self._download_status = self._download_status[-20000:]
        self.downloadChanged.emit()

    def _on_video_percent(self, percent: int) -> None:
        lo, hi = (0, 85) if self._subtitle_leg_wanted else (0, 100)
        value = max(0, min(100, int(percent)))
        self._progress = lo + (hi - lo) * value // 100
        self.downloadChanged.emit()

    def _on_leg_done(self, payload: str) -> None:
        if self._payload_token(payload) != self._op_gen:
            return
        kind, _, rest = payload.split("|", 1)[-1].partition(":")
        if kind == "video":
            self._video_worker = None
        elif kind == "subtitle":
            self._sub_worker = None
        if kind in self._pending:
            self._pending.remove(kind)

        # DownloadWorker emits ``DONE:`` / ``CANCEL:`` / ``ERROR:``; the prefix
        # is everything before the token. Read it instead of hard-coding a name:
        # a mismatched prefix made every failed leg report "ok" and recorded the
        # exception text as a saved file path.
        status_prefix = payload.split("|", 1)[0].split(":", 1)[0]
        cancelled = status_prefix == "CANCEL"
        failed = status_prefix == "ERROR"
        if kind == "video":
            if cancelled:
                self._video_outcome = "cancelled"
                self._download_status += "[canceled] video download stopped.\n"
            elif failed:
                self._video_outcome = "failed"
                message = rest.strip()
                self._download_error = message
                self._download_status += f"[error] {message}\n"
            else:
                self._video_outcome = "ok"
                self._downloaded_video = rest.strip()
                self._progress = 85 if self._subtitle_leg_wanted else 100
                self._download_status += f"[ok] saved: {self._downloaded_video}\n"
                self._record(self._downloaded_video, "video")
        else:
            if cancelled:
                self._subtitle_outcome = "cancelled"
                self._download_status += "[canceled] subtitle download stopped.\n"
            elif failed:
                self._subtitle_outcome = "failed"
                message = rest.strip()
                self._download_error = message
                self._download_status += f"[error] {message}\n"
            else:
                self._subtitle_outcome = "ok"
                self._downloaded_subtitle = rest.strip()
                self._download_status += f"[ok] saved: {self._downloaded_subtitle}\n"
                self._record(self._downloaded_subtitle, "subtitle")

        self.downloadChanged.emit()

        if self._cancel_requested:
            self._finish_operation()
            return
        if kind == "video" and self._subtitle_leg_wanted and self._subtitle_outcome == "":
            # A failed video leg must not suppress the subtitle leg.
            self._start_subtitle_leg()
            return
        if not self._pending:
            self._finish_operation()

    def _finish_operation(self) -> None:
        if not self._download_running:
            return
        self._download_running = False
        self._stage = "done"
        if self._video_outcome == "ok" or self._subtitle_outcome == "ok":
            self._progress = 100
            self._set_status_state(STATUS_DONE)
        elif self._cancel_requested or "cancelled" in (self._video_outcome, self._subtitle_outcome):
            self._set_status_state(STATUS_CANCELLED)
        else:
            self._set_status_state(STATUS_FAILED)

        parts = []
        if self._video_outcome == "ok":
            parts.append("video")
        if self._subtitle_outcome == "ok":
            parts.append(f"subtitle ({self._selected_subtitle})")
        if parts:
            message = "Saved " + " and ".join(parts) + "."
        elif self._cancel_requested:
            message = "Download cancelled."
        else:
            message = "Download failed."
        if self._download_error and not parts:
            message += " " + self._download_error.splitlines()[0][:200]
        self._set_status(message)
        self.downloadChanged.emit()

    @Slot()
    def cancelDownload(self) -> None:
        if not self._download_running:
            return
        self._cancel_requested = True
        self._download_status += "[info] canceling download…\n"
        for worker in (self._video_worker, self._sub_worker):
            if worker is not None:
                worker.cancel()
        self.downloadChanged.emit()

    @Slot()
    def openDownloadFolder(self) -> None:
        self.openFolderForPath(self.downloadDir)

    # ------------------------------------------------------------- library
    def _record(self, path: str, kind: str) -> None:
        if not path:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if kind == "video":
            detail = self.selectedFormatLabel or "video"
        else:
            detail = self.selectedSubtitleLabel
        entry = store.make_entry(
            path=path,
            kind=kind,
            title=self._title,
            video_id=self._video_id,
            url=self.url,
            detail=detail,
            size=size,
            duration=self._duration if kind == "video" else 0,
        )
        self._history = [e for e in self._history if e.get("path") != path]
        self._history.insert(0, entry)
        self._history = self._history[:200]
        store.save_history(self._settings, self._history)
        self.historyChanged.emit()

    @Property(list, notify=historyChanged)
    def history(self) -> list:
        rows = []
        for index, entry in enumerate(self._history):
            rows.append({
                "index": index,
                "name": os.path.basename(str(entry.get("path") or "")),
                "path": entry.get("path") or "",
                "folder": os.path.dirname(str(entry.get("path") or "")),
                "kind": entry.get("kind") or "",
                "kindLabel": "Video" if entry.get("kind") == "video" else "Subtitle",
                "detail": entry.get("detail") or "",
                "sizeText": format_bytes(entry.get("size") or 0),
                "when": entry.get("when") or "",
                "exists": os.path.isfile(str(entry.get("path") or "")),
                "thumbnail": cached_thumbnail(str(entry.get("videoId") or "")),
                "duration": int(entry.get("duration") or 0),
                "selected": index == self._selected_history,
            })
        return rows

    @Property(int, notify=historyChanged)
    def historyCount(self) -> int:
        return len(self._history)

    @Property(int, notify=historyChanged)
    def selectedHistoryIndex(self) -> int:
        return self._selected_history

    @Slot(int)
    def selectHistory(self, index: int) -> None:
        if 0 <= index < len(self._history):
            self._selected_history = index
        else:
            self._selected_history = -1
        self.historyChanged.emit()

    @Slot(int)
    def openDownloadedFile(self, index: int) -> None:
        entry = self._entry(index)
        if entry:
            self.openFolderForPath(entry["path"])

    @Slot(int)
    def openDownloadedFolder(self, index: int) -> None:
        entry = self._entry(index)
        if entry:
            self.openFolderForPath(os.path.dirname(entry["path"]))

    @Slot(int)
    def copyDownloadPath(self, index: int) -> None:
        entry = self._entry(index)
        if entry:
            QGuiApplication.clipboard().setText(entry["path"])
            self._set_status("Path copied.")

    @Slot(int)
    def redownload(self, index: int) -> None:
        entry = self._entry(index)
        if not entry:
            return
        if entry.get("kind") == "subtitle":
            self.selectedSubtitleTrack = self._track_code_from_label(entry.get("detail", ""))
            if not self._selected_subtitle:
                self._set_status("Pick the subtitle track on the Download screen.")
                return
            self.downloadSubtitleOnly()
        else:
            self.download()

    def _track_code_from_label(self, label: str) -> str:
        for track in self._subtitle_tracks:
            if track.get("label") == label:
                return str(track.get("code") or "")
        return ""

    def _entry(self, index: int) -> dict | None:
        if 0 <= index < len(self._history):
            return self._history[index]
        return None

    @Slot()
    def clearHistory(self) -> None:
        self._history = []
        self._selected_history = -1
        store.save_history(self._settings, self._history)
        self.historyChanged.emit()
        self._set_status("Download history cleared.")

    # ------------------------------------------------------------ settings
    @Property(str, notify=themeChanged)
    def themeName(self) -> str:
        return self._theme_name

    @themeName.setter
    def themeName(self, value: str) -> None:
        value = "light" if str(value).lower() == "light" else "dark"
        if value != self._theme_name:
            self._theme_name = value
            self.themeChanged.emit()
            self._notify_form_changed()

    @Slot()
    def toggleTheme(self) -> None:
        self.themeName = "light" if self._theme_name == "dark" else "dark"

    @Property(list, notify=themeChanged)
    def accentChoices(self) -> list:
        return [
            {"id": "iris", "label": "Iris", "dark": "#8A6BFF", "light": "#5B3DF5"},
            {"id": "azure", "label": "Azure", "dark": "#4EA8FF", "light": "#1D69C5"},
            {"id": "mint", "label": "Mint", "dark": "#3DD68C", "light": "#0E7948"},
            {"id": "amber", "label": "Amber", "dark": "#F5A623", "light": "#985B00"},
            {"id": "rose", "label": "Rose", "dark": "#FF5F6D", "light": "#C72E3C"},
        ]

    @Property(str, notify=themeChanged)
    def accentName(self) -> str:
        return self._accent_name

    @accentName.setter
    def accentName(self, value: str) -> None:
        known = {choice["id"] for choice in self.accentChoices}
        value = str(value or "iris")
        if value not in known:
            value = "iris"
        if value != self._accent_name:
            self._accent_name = value
            self.themeChanged.emit()
            self._notify_form_changed()

    @Slot(str)
    def setAccent(self, value: str) -> None:
        self.accentName = value

    @Property(bool, notify=themeChanged)
    def comfortable(self) -> bool:
        return self._comfortable

    @comfortable.setter
    def comfortable(self, value: bool) -> None:
        if bool(value) != self._comfortable:
            self._comfortable = bool(value)
            self.themeChanged.emit()
            self._notify_form_changed()

    @Slot(bool)
    def setComfortable(self, value: bool) -> None:
        self.comfortable = value

    @Property(bool, notify=themeChanged)
    def reducedMotion(self) -> bool:
        return self._reduced_motion

    @reducedMotion.setter
    def reducedMotion(self, value: bool) -> None:
        if bool(value) != self._reduced_motion:
            self._reduced_motion = bool(value)
            self.themeChanged.emit()
            self._notify_form_changed()

    @Slot(bool)
    def setReducedMotion(self, value: bool) -> None:
        self.reducedMotion = value

    # ----------------------------------------------------------- readiness
    @Property(list, notify=readinessChanged)
    def readinessRows(self) -> list:
        ytdlp_ok = yt_dlp_available()
        ffmpeg_ok = media_source._ffmpeg_exe() is not None
        output_ok = _is_writable_dir(self.downloadDir) or os.path.isdir(self.downloadDir)
        return [
            {
                "id": "ytdlp",
                "label": "yt-dlp",
                "state": READINESS_OK if ytdlp_ok else READINESS_TODO,
                "detail": "available" if ytdlp_ok else "not found",
                "hint": "" if ytdlp_ok else "Install it with: pip install yt-dlp",
                "actionable": not ytdlp_ok,
            },
            {
                "id": "ffmpeg",
                "label": "ffmpeg",
                "state": READINESS_OK if ffmpeg_ok else READINESS_TODO,
                "detail": "available" if ffmpeg_ok else "not found",
                "hint": "" if ffmpeg_ok else "Install imageio-ffmpeg, or put ffmpeg.exe on PATH.",
                "actionable": not ffmpeg_ok,
            },
            {
                "id": "output",
                "label": "Download folder",
                "state": READINESS_OK if output_ok else READINESS_TODO,
                "detail": self.downloadDir,
                "hint": "" if output_ok else "Choose a folder you can write to.",
                "actionable": not output_ok,
            },
        ]

    @Property(int, notify=readinessChanged)
    def readinessReadyCount(self) -> int:
        return sum(1 for row in self.readinessRows if row["state"] == READINESS_OK)

    @Property(int, notify=readinessChanged)
    def readinessActionableCount(self) -> int:
        return sum(1 for row in self.readinessRows if row["actionable"])

    @Property(int, notify=readinessChanged)
    def readinessNotApplicableCount(self) -> int:
        return sum(1 for row in self.readinessRows if row["state"] == READINESS_NA)

    @Property(str, notify=readinessChanged)
    def blockedReason(self) -> str:
        for row in self.readinessRows:
            if row["actionable"] and row["state"] == READINESS_TODO:
                return row["hint"] or row["label"]
        return ""

    # ------------------------------------------------------------- failure
    @Property(str, notify=failureChanged)
    def failureCode(self) -> str:
        return self._failure_code

    @Property(str, notify=failureChanged)
    def failureTitle(self) -> str:
        return self._failure_title

    @Property(str, notify=failureChanged)
    def failureDetail(self) -> str:
        return self._failure_detail

    @Property(str, notify=failureChanged)
    def failureRemediation(self) -> str:
        return self._failure_remediation

    @Property(bool, notify=failureChanged)
    def failureActive(self) -> bool:
        return bool(self._failure_title)

    def _set_failure(self, code: str, title: str, detail: str, remedy: str) -> None:
        self._failure_code = code
        self._failure_title = title
        self._failure_detail = detail
        self._failure_remediation = remedy
        self.failureChanged.emit()

    @Slot()
    def dismissFailure(self) -> None:
        self._failure_code = ""
        self._failure_title = ""
        self._failure_detail = ""
        self._failure_remediation = ""
        self.failureChanged.emit()

    # -------------------------------------------------------------- helpers
    @Slot(str, result=str)
    def folderUrl(self, path: str) -> str:
        target = (path or "").strip()
        if not target:
            return ""
        folder = target if os.path.isdir(target) else os.path.dirname(os.path.abspath(target))
        if not os.path.isdir(folder):
            return ""
        return QUrl.fromLocalFile(folder).toString()

    @Slot(str, result=str)
    def fileUrl(self, path: str) -> str:
        target = (path or "").strip()
        if not target:
            return ""
        return QUrl.fromLocalFile(target).toString()

    @Slot(str, result=str)
    def localPath(self, url_or_path: str) -> str:
        text = (url_or_path or "").strip()
        if text.startswith("file:"):
            return QUrl(text).toLocalFile()
        return text

    @Slot(str, result=str)
    def formatBytes(self, size: int) -> str:
        return format_bytes(size)

    @Slot(str)
    def openFolderForPath(self, path: str) -> None:
        target = (path or "").strip()
        if not target:
            return
        folder = target if os.path.isdir(target) else os.path.dirname(target)
        if not folder or not os.path.isdir(folder):
            self._set_status(f"Folder not found: {target}")
            return
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            self._set_status(f"Could not open: {folder}")

    # ------------------------------------------------------------- window
    @Slot(str)
    def saveWindowState(self, geometry: str) -> None:
        parts = [p.strip() for p in (geometry or "").split(",")]
        if len(parts) != 4:
            return
        try:
            self._win_x, self._win_y, self._win_w, self._win_h = (int(p) for p in parts)
        except ValueError:
            return
        self._persist_fields()

    @Property(int, constant=True)
    def windowX(self) -> int:
        return self._win_x

    @Property(int, constant=True)
    def windowY(self) -> int:
        return self._win_y

    @Property(int, constant=True)
    def windowWidth(self) -> int:
        return self._win_w

    @Property(int, constant=True)
    def windowHeight(self) -> int:
        return self._win_h

    # ---------------------------------------------------------- shortcuts
    def _loaded_shortcuts(self) -> dict:
        try:
            values = json.loads(self._shortcuts_json or "{}")
        except (TypeError, ValueError):
            values = {}
        merged = dict(_SHORTCUT_DEFAULTS)
        for key, value in values.items():
            if key in merged and isinstance(value, str):
                merged[key] = value
        return merged

    @Property("QVariantMap", notify=shortcutsChanged)
    def shortcutMap(self) -> dict:
        return self._loaded_shortcuts()

    @Property("QVariantList", notify=shortcutsChanged)
    def shortcutRows(self) -> list:
        values = self._loaded_shortcuts()
        return [
            {"action": action, "label": label, "sequence": values.get(action, "")}
            for action, label in _SHORTCUT_LABELS.items()
        ]

    @Slot(str, result=str)
    def shortcutFor(self, action: str) -> str:
        return self._loaded_shortcuts().get(action, "")

    @Slot(str, str, result=str)
    def setShortcut(self, action: str, sequence: str) -> str:
        values = self._loaded_shortcuts()
        if action not in values:
            return "Unknown action."
        sequence = (sequence or "").strip()
        for other, bound in values.items():
            if other != action and bound == sequence and sequence:
                return "That shortcut is already in use."
        values[action] = sequence
        changed = {k: v for k, v in values.items() if v != _SHORTCUT_DEFAULTS.get(k)}
        self._shortcuts_json = json.dumps(changed)
        self._notify_form_changed()
        self.shortcutsChanged.emit()
        return ""

    @Slot(str)
    def resetShortcut(self, action: str) -> None:
        self.setShortcut(action, _SHORTCUT_DEFAULTS.get(action, ""))

    @Slot()
    def resetAllShortcuts(self) -> None:
        self._shortcuts_json = json.dumps({})
        self._notify_form_changed()
        self.shortcutsChanged.emit()

    # ------------------------------------------------------------- about
    @Property(str, constant=True)
    def appVersion(self) -> str:
        return APP_VERSION

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_NAME

    @Property("QVariantList", constant=True)
    def environmentRows(self) -> list:
        return [
            {"label": "App folder", "value": base_dir()},
            {"label": "Settings store", "value": self._settings.fileName()},
            {"label": "Log file", "value": os.path.join(base_dir(), "saaaveit.log")},
            {"label": "yt-dlp", "value": "available" if yt_dlp_available() else "not found"},
            {"label": "Python", "value": sys.version.split()[0]},
        ]

    @Property(str, constant=True)
    def pathsInUse(self) -> str:
        return (
            f"App: {base_dir()}\n"
            f"Downloads: {self.downloadDir}\n"
            f"Settings: {self._settings.fileName()}\n"
            f"Log: {os.path.join(base_dir(), 'saaaveit.log')}"
        )

    @Slot()
    def clearStoredSettings(self) -> None:
        self._settings.clear()
        self._settings.sync()
        self._load_persisted()
        self._set_status("Stored settings cleared.")
