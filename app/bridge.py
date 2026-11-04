"""The QML bridge for the Saaaveit downloader.

One object, exposed to QML as ``appBridge``. It owns:

  * inspection state (formats + subtitle tracks for the current URL),
  * the download queue: many jobs, run strictly one at a time, each as a video
    leg then the subtitle leg it was queued with,
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
from .queue import (
    CANCELLED,
    DONE,
    FAILED,
    QUEUED,
    RUNNING,
    TERMINAL,
    QueueJob,
)

APP_NAME = "Saaaveit"
APP_VERSION = "1.0.0"
# The brand hue, and the value Theme.qml falls back to. Kept in sync with the
# first entry of ``Theme.accentChoices`` by tests/test_theme_contrast.py.
DEFAULT_ACCENT = "cobalt"

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

# The filename-template preview stands a sample video in for the one that has
# not been inspected yet. Same shape as the reference's own example.
_TEMPLATE_SAMPLE_FIELDS = {
    "title": "How Compilers Turn Code into Machines",
    "id": "c0mP1l3r",
    "ext": "mp4",
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


def register_bundled_fonts() -> None:
    """Add the vendored ``ui/fonts`` TTFs to the application font database.

    ``Theme.qml`` names "Hanken Grotesk" and "IBM Plex Mono" first and falls
    back to system fonts, so forgetting this only changes the look, never the
    launch. Both families are SIL OFL 1.1 (``ui/fonts/README.md``). The offscreen
    tools and the test harness call it too, so what is reviewed is what ships.
    """
    from PySide6.QtGui import QFontDatabase

    base = getattr(sys, "_MEIPASS", None) or base_dir()
    fonts_dir = os.path.join(base, "ui", "fonts")
    if not os.path.isdir(fonts_dir):
        return
    for name in sorted(os.listdir(fonts_dir)):
        if name.lower().endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(fonts_dir, name))


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
    queueChanged = Signal()
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
        ("_default_subtitle_track", "downloads/subtitleTrack", "none"),
        ("_preferred_codec", "downloads/preferredCodec", ""),
        ("_preferred_resolution", "downloads/preferredResolution", ""),
        ("_filename_template", "downloads/filenameTemplate", DEFAULT_FILENAME_TEMPLATE),
        ("_theme_name", "ui/theme", "dark"),
        ("_accent_name", "ui/accent", DEFAULT_ACCENT),
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
        self._pending_redownload = None
        self._info_worker: InfoWorker | None = None
        self._info_gen = 0

        # --- the download queue -------------------------------------------
        # Downloads get a pool of their own, capped at one thread, so two jobs
        # can never be in flight even if a bug let the pump start a second one.
        # Inspection keeps ``self.threadpool``: a job may run for minutes and
        # the form must stay usable behind it. See ``app/queue.py`` for why
        # parallel downloads are wrong for this engine rather than merely
        # unimplemented.
        self._download_pool = QThreadPool()
        self._download_pool.setMaxThreadCount(1)
        self._op_gen = 0
        self._job_seq = 0
        self._queue: list[QueueJob] = []
        self._active: QueueJob | None = None
        # The finished job the scalar download properties fall back to once the
        # queue drains, so the panel still reports what the last one did.
        self._last: QueueJob | None = None
        self._video_worker: DownloadWorker | None = None
        self._sub_worker: DownloadWorker | None = None
        self._download_running = False
        self._cancel_requested = False
        # A refusal that never produced a job still has to reach the panel that
        # reports the last attempt, so the reason is parked here and cleared
        # when a job actually starts.
        self._preflight_notice = ""
        self._preflight_error = ""

        # --- settings / chrome -------------------------------------------
        self._download_dir = ""
        self._default_subtitle_track = "none"
        self._preferred_codec = ""
        self._preferred_resolution = ""
        self._filename_template = DEFAULT_FILENAME_TEMPLATE
        self._theme_name = "dark"
        self._accent_name = DEFAULT_ACCENT
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
            # ``setattr`` above bypasses the property setters, so a stale or
            # hand-edited store could boot the chrome into a hue or mode that
            # does not exist. Fall back to the brand defaults instead.
            if self._accent_name not in {c["id"] for c in self.accentChoices}:
                self._accent_name = DEFAULT_ACCENT
            if self._theme_name not in ("dark", "light"):
                self._theme_name = "dark"
            self._history = store.load_history(self._settings)
            self._load_queue()
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

    @Slot(result=str)
    def clipboardText(self) -> str:
        """The clipboard's first non-empty line, for the Paste button.

        Returned rather than assigned: the URL field must show the text too,
        and a programmatic ``text`` change does not fire ``onTextEdited``, so
        QML sets the bridge explicitly.
        """
        for line in (QGuiApplication.clipboard().text() or "").splitlines():
            if line.strip():
                return line.strip()
        return ""

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
        self._last = None
        self.inspectChanged.emit()
        self.downloadChanged.emit()

    # --------------------------------------------------------- inspection
    @Slot()
    def inspect(self) -> None:
        url = self._url.strip()
        if not url:
            self._info_error = "Paste a video URL first."
            self.inspectChanged.emit()
            return
        if self._info_loading:
            return
        self._info_loading = True
        self._info_error = ""
        # A new inspection supersedes the last failure.
        self.dismissFailure()
        self._matrix = {}
        self._best = {}
        self._codecs = []
        self._resolutions = []
        self._subtitle_tracks = []
        self._selected_codec = "best"
        self._selected_resolution = "best"
        self._selected_subtitle = ""
        # A fresh video must not inherit the last job's completion: the panel
        # reports on ``_last`` while nothing runs, and a 100% green bar over an
        # inspection is a lie.
        self._last = None
        self.inspectChanged.emit()
        self.downloadChanged.emit()
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
            self._pending_redownload = None
            self._info_error = payload.split("|", 1)[-1].strip()
            self.inspectChanged.emit()
            self._set_status(self._info_error)
            self._set_status_state(STATUS_FAILED)
            return
        try:
            info = json.loads(payload.split("|", 1)[-1])
        except (ValueError, TypeError):
            self._pending_redownload = None
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
        except (TypeError, ValueError, OverflowError):
            # A payload from an older worker (or a live stream reporting
            # ``Infinity``) must not abort the rest of the inspection.
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
        # The finished job that still colours the summary bar belongs to the
        # previous video; this one starts at zero.
        self._last = None
        preference_notice = self._apply_format_preference(info)
        self._selected_subtitle = self._default_track_for(info)
        # The fresh result has landed: whatever failed before belongs to a
        # superseded attempt.
        self.dismissFailure()
        self.inspectChanged.emit()
        self.downloadChanged.emit()
        status = (
            f"Inspected “{self._title}” — {len(self._codecs)} codec(s), "
            f"{len(self._resolutions)} resolution(s), "
            f"{len(self._subtitle_tracks)} subtitle track(s)."
        )
        if preference_notice:
            status = f"{status} {preference_notice}"
            self._append_log(f"[warn] {preference_notice}\n")
        self._set_status(status)
        self._set_status_state(STATUS_READY)
        # After the inspection status: a redownload that refuses to start
        # ("that track is no longer offered") must overwrite it, not be
        # overwritten by it.
        self._run_pending_redownload()

    def _default_track_for(self, info: dict) -> str:
        mode = (self._default_subtitle_track or "none").strip().lower()
        tracks = info.get("subtitle_tracks") or []
        if mode == "none":
            return ""
        if mode == "original":
            return str(info.get("default_subtitle_track") or "")
        for track in tracks:
            if track.get("kind") == mode:
                return str(track.get("code") or "")
        return ""

    def _apply_format_preference(self, info: dict) -> str:
        """Preselect the remembered codec/resolution; return a warning if not served.

        An unset preference keeps the historic behaviour: the first offered
        codec at Best resolution. The preference is only ever written by the
        first download or by Settings, so a video that cannot serve it is the
        exception and must say so rather than silently disagreeing.
        """
        codec = (self._preferred_codec or "").strip().lower()
        resolution = str(self._preferred_resolution or "").strip().lower()
        fallback = self._codecs[0] if self._codecs else "best"
        if not codec:
            self._selected_codec = fallback
            self._selected_resolution = "best"
            return ""
        if codec == "best":
            self._selected_codec = "best"
            self._selected_resolution = "best"
            return ""
        if codec not in self._codecs:
            self._selected_codec = fallback
            self._selected_resolution = "best"
            return (
                f"This video has no {codec.upper()} streams — showing "
                f"{fallback.upper()} at Best instead. Change it in step 2 "
                "or under Settings → Preferred format."
            )
        self._selected_codec = codec
        wanted = media_source.normalize_resolution(resolution)
        if wanted == "best":
            self._selected_resolution = "best"
            return ""
        family = self._matrix.get(codec) or {}
        if str(wanted) in {str(h) for h in family}:
            self._selected_resolution = wanted
            return ""
        self._selected_resolution = "best"
        return (
            f"This video has no {codec.upper()} at {wanted}p — resolution "
            "reset to Best. Change it in step 2 or under Settings → Preferred format."
        )

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

    @Slot()
    def copyVideoId(self) -> None:
        if not self._video_id:
            return
        QGuiApplication.clipboard().setText(self._video_id)
        self._set_status("Video ID copied.")

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

    @Slot(str, "QVariant")
    def pickFormat(self, codec: str, resolution) -> None:
        """Select one matrix cell, both halves at once.

        ``selectedCodec``'s setter demotes the resolution to "best" when the new
        codec has no such row, so a cell click written as two property
        assignments loses one of them depending on the order. The matrix hands
        ``resolution`` through as either an int (1080) or the string "best",
        which is why it is normalised here rather than by the caller.
        """
        codec = (codec or "best").strip() or "best"
        wanted = media_source.normalize_resolution(resolution)
        family = self._matrix.get(codec) or {}
        if family and wanted != "best" and str(wanted) not in {str(h) for h in family}:
            wanted = "best"
        if codec == self._selected_codec and wanted == self._selected_resolution:
            return
        self._selected_codec = codec
        self._selected_resolution = wanted
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
        self._set_field("_default_subtitle_track", (value or "none").strip())

    @Property(list, notify=formChanged)
    def defaultSubtitleChoices(self) -> list:
        return [
            {"id": "none", "label": "None — video only (default)"},
            {"id": "original", "label": "Original language"},
            {"id": "manual", "label": "First manual track"},
            {"id": "auto", "label": "First auto-generated track"},
        ]

    # ------------------------------------------------- preferred format pick
    @Property(str, notify=formChanged)
    def preferredCodec(self) -> str:
        return self._preferred_codec

    @preferredCodec.setter
    def preferredCodec(self, value: str) -> None:
        self._set_field("_preferred_codec", (value or "").strip().lower())

    @Property(str, notify=formChanged)
    def preferredResolution(self) -> str:
        return self._preferred_resolution

    @preferredResolution.setter
    def preferredResolution(self, value) -> None:
        # "best" and "" behave identically in the preselection, so they
        # collapse to one stored value the Settings combo can round-trip.
        text = media_source.normalize_resolution(value)
        self._set_field("_preferred_resolution", "" if text == "best" else text)

    @Property(list, notify=formChanged)
    def preferredCodecChoices(self) -> list:
        return [
            {"id": "", "label": "No preference"},
            {"id": "best", "label": "Best available"},
            {"id": "av1", "label": "AV1"},
            {"id": "vp9", "label": "VP9"},
            {"id": "h264", "label": "H.264"},
        ]

    @Property(list, notify=formChanged)
    def preferredResolutionChoices(self) -> list:
        return [
            {"id": "", "label": "No preference"},
            {"id": "2160", "label": "2160p"},
            {"id": "1440", "label": "1440p"},
            {"id": "1080", "label": "1080p"},
            {"id": "720", "label": "720p"},
            {"id": "480", "label": "480p"},
            {"id": "360", "label": "360p"},
        ]

    @Property(str, notify=formChanged)
    def filenameTemplate(self) -> str:
        return self._filename_template

    @filenameTemplate.setter
    def filenameTemplate(self, value: str) -> None:
        self._set_field("_filename_template", (value or "").strip() or DEFAULT_FILENAME_TEMPLATE)

    def render_template(self, template: str) -> str:
        """Fill a filename template with sample values, leaving unknown fields.

        The Settings card previews a template before any video is inspected, so
        the sample has to be the thing that stands in for a real title. A field
        this app does not know (``%(uploader)s``) stays literal: silently
        dropping it would hide a typo from the person who just typed it.
        """
        template = (template or "").strip() or DEFAULT_FILENAME_TEMPLATE
        known = _TEMPLATE_SAMPLE_FIELDS

        def fill(match):
            key = match.group(1)
            return known.get(key, match.group(0))

        rendered = re.sub(r"%\((\w+)\)s", fill, template)
        if "%(ext)s" not in template:
            rendered += ".mp4"
        return rendered

    @Property(str, notify=formChanged)
    def filenamePreview(self) -> str:
        return self.render_template(self._filename_template)

    def _out_template(self) -> str:
        return os.path.join(self.downloadDir, self._filename_template)

    # ------------------------------------------------------------ download
    def _shown(self) -> QueueJob | None:
        """The job the scalar download properties report on.

        While a job runs that is the active one; once the queue drains the
        panel still has to say what the last job did, so it falls back to it.
        """
        return self._active or self._last

    def _shown_field(self, name: str, default=None):
        job = self._shown()
        return getattr(job, name, default) if job is not None else default

    @Property(bool, notify=downloadChanged)
    def downloadRunning(self) -> bool:
        return self._download_running

    @Property(int, notify=downloadChanged)
    def downloadProgress(self) -> int:
        return int(self._shown_field("progress", 0))

    @Property(str, notify=downloadChanged)
    def downloadStage(self) -> str:
        return self._shown_field("stage", "")

    @Property(str, notify=downloadChanged)
    def downloadStatus(self) -> str:
        return self._shown_field("status", "")

    @Property(str, notify=downloadChanged)
    def downloadNotice(self) -> str:
        return self._preflight_notice or self._shown_field("notice", "")

    @Property(str, notify=downloadChanged)
    def downloadError(self) -> str:
        return self._preflight_error or self._shown_field("error", "")

    @Property(str, notify=downloadChanged)
    def videoOutcome(self) -> str:
        return self._shown_field("video_outcome", "")

    @Property(str, notify=downloadChanged)
    def subtitleOutcome(self) -> str:
        return self._shown_field("subtitle_outcome", "")

    @Property(str, notify=downloadChanged)
    def downloadedVideo(self) -> str:
        return self._shown_field("saved_video", "")

    @Property(str, notify=downloadChanged)
    def downloadedSubtitle(self) -> str:
        return self._shown_field("saved_subtitle", "")

    @Property(bool, notify=canDownloadChanged)
    def canDownload(self) -> bool:
        """Whether the current picks are worth committing to the queue.

        A download in flight does not block this: joining the batch is the
        whole point, and ``primaryAction`` tells the button what it means now.
        """
        return bool(self.hasInfo and self.url
                    and self.selectedOption.get("format_selector"))

    # ---------------------------------------------------------------- queue
    @Property(int, notify=queueChanged)
    def queueCount(self) -> int:
        return len(self._queue)

    @Property(int, notify=queueChanged)
    def pendingCount(self) -> int:
        return sum(1 for job in self._queue if job.state == QUEUED)

    @Property(str, notify=queueChanged)
    def primaryAction(self) -> str:
        """What the primary button means right now, so QML never re-derives it.

        ``download`` starts at once, ``queue`` joins a batch already in flight,
        and ``start`` is the case a restored queue leaves the user in: work is
        waiting and nothing is running.
        """
        if self._active is not None:
            return "queue"
        if self.pendingCount:
            return "start"
        return "download"

    @Property(list, notify=queueChanged)
    def queueRows(self) -> list:
        rows = []
        total = len(self._queue)
        for index, job in enumerate(self._queue):
            rows.append({
                "index": index,
                "id": job.id,
                "name": job.name,
                "title": job.title,
                "url": job.url,
                "videoId": job.video_id,
                "thumbnail": job.thumbnail,
                "state": job.state,
                "stateLabel": job.state_label,
                "outcome": job.outcome,
                "progress": job.progress,
                "stage": job.stage,
                "position": index + 1,
                "total": total,
                "formatLabel": job.format_label,
                "subtitleLabel": job.subtitle_label if job.subtitle_leg_wanted else "",
                "summary": job.summary,
                "error": job.error,
                "notice": job.notice,
                "status": job.status,
                "savedVideo": job.saved_video,
                "savedSubtitle": job.saved_subtitle,
                "downloadDir": job.download_dir,
                "active": job is self._active,
                "waiting": job.state == QUEUED,
                "removable": job.is_terminal,
            })
        return rows

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
        """Queue the selected video format and, if one is selected, a subtitle.

        Starts at once when nothing is in flight; otherwise it joins the batch.
        """
        job = self._capture_job(include_subtitle=True)
        if job is None:
            return
        self._enqueue(job)

    @Slot()
    def downloadSubtitleOnly(self) -> None:
        """Queue just the selected subtitle track (the video is already on disk)."""
        if not self._selected_subtitle:
            self._set_status("Select a subtitle track first.")
            return
        job = self._capture_job(include_subtitle=True, video=False)
        if job is None:
            return
        self._enqueue(job)

    @Slot()
    def runPrimaryAction(self) -> None:
        """Do whatever ``primaryAction`` says the primary button currently means."""
        if self.primaryAction == "start":
            self.startQueue()
        else:
            self.download()

    @Slot()
    def startQueue(self) -> None:
        """Begin work on a queue that is waiting but idle."""
        self._pump()

    def _capture_job(self, *, include_subtitle: bool, video: bool = True) -> QueueJob | None:
        """Freeze the current picks into a job, or refuse with a reason.

        Everything the download needs is read here and never again: after this
        returns the user is free to inspect another video, and the job must
        still fetch what was chosen when they queued it.
        """
        if not self.url:
            self._set_status("Paste a video URL first.")
            return None
        subtitle_lang = self._selected_subtitle if include_subtitle else ""
        if video:
            selector = self._selector()
            if not selector:
                reason = self.selectionError or (
                    "This video is not available in the selected format."
                )
                self._preflight_notice = reason
                self._preflight_error = reason
                self.downloadChanged.emit()
                self._set_status(reason)
                self._set_status_state(STATUS_FAILED)
                self._set_failure(
                    "format",
                    "That pick has no stream",
                    reason,
                    "Choose another cell in step 2 - or use Best available.",
                )
                return None
        elif not subtitle_lang:
            return None

        return QueueJob(
            id=self._next_job_id(),
            url=self._url.strip(),
            kind="video" if video else "subtitle",
            video_id=self._video_id,
            title=self._title,
            thumbnail=self._thumbnail,
            duration=self._duration,
            codec=self._selected_codec,
            resolution=str(self._selected_resolution),
            format_selector=self._selector(),
            format_label=self.selectedFormatLabel,
            expect=self._expectation(),
            out_base=self._out_template(),
            download_dir=self.downloadDir,
            subtitle_lang=subtitle_lang,
            subtitle_kind=self._selected_subtitle_kind(),
            subtitle_label=self.selectedSubtitleLabel if subtitle_lang else "",
            subtitle_leg_wanted=bool(subtitle_lang),
        )

    def _next_job_id(self) -> int:
        self._job_seq += 1
        return self._job_seq

    def _duplicate_of(self, job: QueueJob) -> QueueJob | None:
        """The pending job this one repeats, if there is one.

        Matched on video, stream and track. Finished rows do not block: the
        clash worth refusing is two jobs racing to write the same file, and a
        row that already saved is a record rather than work. The library is
        deliberately not consulted either — re-fetching something downloaded
        last month at a different resolution is a decision, not a mistake.
        """
        key = job.duplicate_key()
        for other in self._queue:
            if other.state in TERMINAL:
                continue
            if other.duplicate_key() == key:
                return other
        return None

    def _enqueue(self, job: QueueJob) -> None:
        clash = self._duplicate_of(job)
        if clash is not None:
            detail = clash.format_label or "the same stream"
            state = "downloading" if clash.state == RUNNING else "still waiting"
            self._set_status(
                f"{clash.name} · {detail} is already {state}. "
                "Drop it from the queue to fetch it again."
            )
            return
        if len(self._queue) >= store.MAX_QUEUE:
            self._set_status(
                f"The queue holds {store.MAX_QUEUE} jobs. Clear some before adding more."
            )
            return
        self._queue.append(job)
        if job.kind == "video" and not self._preferred_codec:
            # The first download establishes the format preference; from then
            # on only Settings changes it. The job's frozen picks are what the
            # user actually committed to, not whatever the form shows now.
            self._preferred_codec = str(job.codec or "")
            wanted = media_source.normalize_resolution(job.resolution)
            self._preferred_resolution = "" if wanted == "best" else wanted
            self._notify_form_changed()
        self._persist_queue()
        self.queueChanged.emit()
        self._pump()

    def _pump(self) -> None:
        """Start the next waiting job, if the lane is free.

        Draining the queue leaves the last job's status line standing; nothing
        here overwrites it, so "Saved video and subtitle" survives its own
        completion.
        """
        if self._active is not None:
            return
        for job in self._queue:
            if job.state == QUEUED:
                self._start_job(job)
                return

    def _start_job(self, job: QueueJob) -> None:
        self._op_gen += 1
        # A new job supersedes the last failure; the banner survives a finish,
        # but a fresh start is a fresh slate.
        self.dismissFailure()
        self._cancel_requested = False
        self._preflight_notice = ""
        self._preflight_error = ""
        self._active = job
        self._download_running = True
        job.state = RUNNING
        job.progress = 0
        job.stage = "preparing"
        job.status = ""
        job.notice = ""
        job.error = ""
        job.saved_video = ""
        job.saved_subtitle = ""
        job.video_outcome = "" if job.kind == "video" else "skipped"
        job.subtitle_outcome = "" if job.subtitle_leg_wanted else "skipped"
        job.pending_legs = []
        self.downloadChanged.emit()
        self.queueChanged.emit()
        self._set_status(self._job_status_line(job))
        self._set_status_state(STATUS_RUNNING)
        if job.kind == "subtitle":
            self._start_subtitle_leg(job)
        else:
            self._start_video_leg(job)

    def _job_position(self, job: QueueJob) -> tuple[int, int]:
        try:
            return self._queue.index(job) + 1, len(self._queue)
        except ValueError:
            return 0, 0

    def _job_status_line(self, job: QueueJob) -> str:
        """The status bar for a running job, naming its place in the batch."""
        position, total = self._job_position(job)
        prefix = f"Downloading {position} of {total} — " if total > 1 else "Downloading — "
        return prefix + (job.name or job.url)

    def _start_video_leg(self, job: QueueJob) -> None:
        job.pending_legs.append("video")
        job.stage = "video"
        job.status += "Preparing video download…\n"
        self.downloadChanged.emit()
        worker = DownloadWorker(
            "video",
            job.url,
            format_selector=job.format_selector,
            out_template=job.out_base + ".%(ext)s",
            token=self._op_gen,
            expect=job.expect,
        )
        worker.signals.progress.connect(self._append_log)
        worker.signals.progress.connect(self._on_download_line)
        worker.signals.percent.connect(self._on_video_percent)
        worker.signals.done.connect(self._on_leg_done)
        self._video_worker = worker
        self._download_pool.start(worker)

    def _start_subtitle_leg(self, job: QueueJob) -> None:
        job.pending_legs.append("subtitle")
        job.stage = "subtitle"
        job.progress = max(job.progress, 85)
        job.status += f"Fetching the {job.subtitle_lang} subtitle track…\n"
        self.downloadChanged.emit()
        worker = DownloadWorker(
            "subtitle",
            job.url,
            out_template=job.out_base,
            token=self._op_gen,
            subtitle_lang=job.subtitle_lang,
            subtitle_kind=job.subtitle_kind,
        )
        worker.signals.progress.connect(self._append_log)
        worker.signals.progress.connect(self._on_download_line)
        worker.signals.done.connect(self._on_leg_done)
        self._sub_worker = worker
        self._download_pool.start(worker)

    def _on_download_line(self, text: str) -> None:
        job = self._active
        if job is None:
            return
        job.status += text
        if text.lstrip().startswith("[warn]"):
            notice = text.strip()[len("[warn]"):].strip()
            if notice:
                job.notice = notice
        lowered = text.lower()
        if "[audio]" in lowered:
            job.stage = "audio"
        elif "merging formats into" in lowered or lowered.startswith("[merger]"):
            job.stage = "merging"
        job.status = job.status[-20000:]
        # ``downloadChanged`` only: the row list is rebuilt wholesale on
        # ``queueChanged``, and a percent line arrives many times a second. The
        # live figures come from the scalar properties, the list carries states.
        self.downloadChanged.emit()

    def _on_video_percent(self, percent: int) -> None:
        job = self._active
        if job is None:
            return
        lo, hi = (0, 85) if job.subtitle_leg_wanted else (0, 100)
        value = max(0, min(100, int(percent)))
        # DASH runs a second 0→100 sweep for the audio fragment; the bar may
        # only ever move forward while one job is active.
        job.progress = max(job.progress, lo + (hi - lo) * value // 100)
        self.downloadChanged.emit()

    def _on_leg_done(self, payload: str) -> None:
        if self._payload_token(payload) != self._op_gen:
            return
        job = self._active
        if job is None:
            return
        kind, _, rest = payload.split("|", 1)[-1].partition(":")
        if kind == "video":
            self._video_worker = None
        elif kind == "subtitle":
            self._sub_worker = None
        if kind in job.pending_legs:
            job.pending_legs.remove(kind)

        # DownloadWorker emits ``DONE:`` / ``CANCEL:`` / ``ERROR:``; the prefix
        # is everything before the token. Read it instead of hard-coding a name:
        # a mismatched prefix made every failed leg report "ok" and recorded the
        # exception text as a saved file path.
        status_prefix = payload.split("|", 1)[0].split(":", 1)[0]
        cancelled = status_prefix == "CANCEL"
        failed = status_prefix == "ERROR"
        if kind == "video":
            if cancelled:
                job.video_outcome = CANCELLED
                job.status += "[canceled] video download stopped.\n"
            elif failed:
                job.video_outcome = FAILED
                message = rest.strip()
                job.error = message
                job.status += f"[error] {message}\n"
                self._classify_failure(message)
            else:
                job.video_outcome = "ok"
                job.saved_video = rest.strip()
                job.progress = 85 if job.subtitle_leg_wanted else 100
                job.status += f"[ok] saved: {job.saved_video}\n"
                self._record(job, job.saved_video, "video")
        else:
            if cancelled:
                job.subtitle_outcome = CANCELLED
                job.status += "[canceled] subtitle download stopped.\n"
            elif failed:
                job.subtitle_outcome = FAILED
                message = rest.strip()
                job.error = message
                job.status += f"[error] {message}\n"
                self._classify_failure(message)
            else:
                job.subtitle_outcome = "ok"
                job.saved_subtitle = rest.strip()
                job.status += f"[ok] saved: {job.saved_subtitle}\n"
                self._record(job, job.saved_subtitle, "subtitle")

        self.downloadChanged.emit()
        self.queueChanged.emit()

        if self._cancel_requested:
            self._finish_job(job)
            return
        if kind == "video" and job.subtitle_leg_wanted and job.subtitle_outcome == "":
            # A failed video leg must not suppress the subtitle leg.
            self._start_subtitle_leg(job)
            return
        if not job.pending_legs:
            self._finish_job(job)

    def _finish_job(self, job: QueueJob) -> None:
        """Close one job out and hand the lane to the next waiting one."""
        if self._active is not job:
            return
        legs = (job.video_outcome, job.subtitle_outcome)
        if self._cancel_requested or CANCELLED in legs:
            # Cancelling the video leg after the subtitle landed still saved
            # something, and the row should say so rather than "cancelled".
            job.state = DONE if "ok" in legs else CANCELLED
        elif "ok" in legs:
            job.state = DONE
        else:
            job.state = FAILED
        if "ok" in legs:
            job.progress = 100
        job.stage = "done"
        job.pending_legs = []

        self._active = None
        self._last = job
        self._download_running = False

        if job.state == DONE:
            self._set_status_state(STATUS_DONE)
        elif job.state == CANCELLED:
            self._set_status_state(STATUS_CANCELLED)
        else:
            self._set_status_state(STATUS_FAILED)

        self._set_status(self._job_message(job))
        self.downloadChanged.emit()
        self.queueChanged.emit()
        self._persist_queue()
        # A failed job does not stop the batch: the point of queueing is that
        # one dead link out of ten costs nothing but its own row.
        self._pump()

    def _job_message(self, job: QueueJob) -> str:
        parts = []
        if job.video_outcome == "ok":
            parts.append("video")
        if job.subtitle_outcome == "ok":
            parts.append(f"subtitle ({job.subtitle_lang})")
        if parts:
            message = "Saved " + " and ".join(parts) + "."
        elif job.state == CANCELLED:
            message = "Download cancelled."
        else:
            message = "Download failed."
        if job.error and not parts:
            message += " " + job.error.splitlines()[0][:200]
        waiting = self.pendingCount
        if waiting:
            message += f" {waiting} still queued."
        return message

    @Slot()
    def cancelDownload(self) -> None:
        """Stop the running job. The queue advances to the next one.

        ``clearQueue`` is the separate intent of dropping the waiting work too.
        """
        if not self._download_running:
            return
        self._cancel_requested = True
        if self._active is not None:
            self._active.status += "[info] canceling download…\n"
        for worker in (self._video_worker, self._sub_worker):
            if worker is not None:
                worker.cancel()
        self.downloadChanged.emit()

    @Slot()
    def clearQueue(self) -> None:
        """Drop every job that is not running. The in-flight one is left alone."""
        kept = [job for job in self._queue if job.state == RUNNING]
        if len(kept) == len(self._queue):
            return
        self._queue = kept
        self._persist_queue()
        self.queueChanged.emit()
        self._set_status("Queue cleared.")

    @Slot(int)
    def cancelJob(self, index: int) -> None:
        """Drop a waiting job, stop the running one, or dismiss a finished row."""
        job = self._job_at(index)
        if job is None:
            return
        if job.state == QUEUED or job.state in TERMINAL:
            # A finished row is only a record of what already happened;
            # dismissing it must not touch the file it points at.
            self._queue.remove(job)
            self._persist_queue()
            self.queueChanged.emit()
            self._set_status(f"Removed {job.name} from the queue.")
        elif job.state == RUNNING:
            self.cancelDownload()

    def _job_at(self, index: int) -> QueueJob | None:
        if 0 <= index < len(self._queue):
            return self._queue[index]
        return None

    def _persist_queue(self) -> None:
        """Store the work still to do.

        A running job is written back as waiting: the bytes it fetched are
        resumable, and a queue that survived a crash must not look finished.
        """
        store.save_queue(
            self._settings,
            [job.to_dict() for job in self._queue if job.state in (QUEUED, RUNNING)],
        )

    def _load_queue(self) -> None:
        """Restore waiting jobs, paused. Nothing starts by itself."""
        self._queue = []
        for raw in store.load_queue(self._settings):
            try:
                job = QueueJob.from_dict(raw)
            except (TypeError, ValueError):
                continue
            job.state = QUEUED
            self._queue.append(job)
        self._job_seq = max((job.id for job in self._queue), default=0)

    @Slot()
    def openDownloadFolder(self) -> None:
        self.openFolderForPath(self.downloadDir)

    # ------------------------------------------------------------- library
    def _record(self, job: QueueJob, path: str, kind: str) -> None:
        """File one saved path in the library, described by the job that made it.

        Every field comes from the snapshot, never the live form: with a queue
        the user has usually moved on to the next video by the time a job
        lands, and reading ``self._title`` here would file it under whatever
        was inspected last.
        """
        if not path:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if kind == "video":
            detail = job.format_label or "video"
        else:
            detail = job.subtitle_label
        entry = store.make_entry(
            path=path,
            kind=kind,
            title=job.title,
            video_id=job.video_id,
            url=job.url,
            detail=detail,
            size=size,
            duration=job.duration if kind == "video" else 0,
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
    def removeHistory(self, index: int) -> None:
        """Drop one entry from the list. The file on disk is never touched."""
        if not 0 <= index < len(self._history):
            return
        del self._history[index]
        if self._selected_history == index:
            self._selected_history = -1
        elif self._selected_history > index:
            # Every row below the removed one moves up; the drawer must follow
            # the same file rather than the row it used to sit in.
            self._selected_history -= 1
        store.save_history(self._settings, self._history)
        self.historyChanged.emit()
        self._set_status("Removed from history. The file stays on disk.")

    @Slot(int)
    def launchFile(self, index: int) -> None:
        """Open the recorded file with its own default handler."""
        entry = self._entry(index)
        if not entry:
            return
        path = str(entry.get("path") or "")
        if not os.path.isfile(path):
            self._set_status(f"File is missing from disk: {os.path.basename(path)}")
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError:
            self._set_status(f"Could not open: {path}")

    @Slot()
    def openLastFile(self) -> None:
        if not self._history:
            self._set_status("Nothing downloaded yet.")
            return
        self.launchFile(0)

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
        """Revisit an entry the way the prototype does.

        Navigate to Download, load the entry's URL, inspect - and then, when
        the inspection lands, queue what was recorded (the video, or that one
        subtitle track). A download already in flight does not block this: the
        new job lines up behind it. The pending note is cleared in
        ``_on_info_done`` on both paths, so it can never double-fire.
        """
        entry = self._entry(index)
        if not entry:
            return
        url = str(entry.get("url") or "").strip()
        if not url:
            self._set_status("That entry was saved without a source URL.")
            return
        self._pending_redownload = {
            "kind": entry.get("kind") or "video",
            "detail": entry.get("detail") or "",
        }
        self.requestTab.emit(0)
        if url == self._url:
            self.inspect()
        else:
            self.url = url

    def _run_pending_redownload(self) -> None:
        pending, self._pending_redownload = self._pending_redownload, None
        if not pending:
            return
        if pending["kind"] == "subtitle":
            code = self._track_code_from_label(pending["detail"])
            if not code:
                self._set_status(
                    "That subtitle track is no longer offered. Pick another "
                    "one on the Download screen.")
                return
            self.selectedSubtitleTrack = code
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
        # Ids and names only. The hexes live in ``Theme.accentChoices``, which
        # is what actually paints — this list used to carry a second, drifted
        # copy, so the swatch you clicked was not the colour you got.
        return [
            {"id": "cobalt", "label": "Cobalt"},
            {"id": "iris", "label": "Iris"},
            {"id": "azure", "label": "Azure"},
            {"id": "mint", "label": "Mint"},
            {"id": "amber", "label": "Amber"},
            {"id": "rose", "label": "Rose"},
        ]

    @Property(str, notify=themeChanged)
    def accentName(self) -> str:
        return self._accent_name

    @accentName.setter
    def accentName(self, value: str) -> None:
        known = {choice["id"] for choice in self.accentChoices}
        value = str(value or DEFAULT_ACCENT)
        if value not in known:
            value = DEFAULT_ACCENT
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

    def _classify_failure(self, message: str) -> None:
        """Turn a worker error line into the banner's four fields.

        The extractor only reads - it never re-raises. An unrecognised error
        still deserves a banner, so the fallback keeps the raw detail and a
        generic remedy rather than swallowing it.
        """
        low = (message or "").lower()
        detail = " ".join((message or "").split())[:420]
        match = re.search(r"http error (\d{3})", low)
        status = match.group(1) if match else ""
        if (status in ("401", "403", "407") or "login required" in low
                or "sign in" in low or "cookies" in low):
            self._set_failure(
                "restricted",
                "This video is gated",
                detail or "The host asked for credentials we do not have.",
                "It may need a sign-in, an older-age check, or a premium "
                "account. Open the link in your browser to confirm; this app "
                "never stores accounts.",
            )
        elif (status in ("404", "410") or "not available" in low
                or "private video" in low or "removed" in low
                or "members only" in low):
            self._set_failure(
                "unavailable",
                "This video is not available",
                detail or "The host says it is gone.",
                "It may be private, deleted, or region-locked. Double-check "
                "the URL, then try a video you know is public.",
            )
        elif ("timed out" in low or "getaddrinfo" in low or "proxy" in low
                or "unable to connect" in low or "network" in low
                or "connection reset" in low or "Temporary failure" in low):
            self._set_failure(
                "network",
                "The network gave up",
                detail or "The connection dropped mid-request.",
                "Check your connection (or proxy) and retry. A part-fetched "
                "file resumes where it stopped.",
            )
        else:
            self._set_failure(
                "error",
                "The download failed",
                detail or "No detail came back from the fetcher.",
                "Open the log for the full error text, fix what it points "
                "at, then retry.",
            )

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
            {
                "action": action,
                "label": label,
                "sequence": values.get(action, ""),
                # A row still on its default has nothing to reset, and the
                # reference disables the button rather than no-op'ing it.
                "isDefault": values.get(action) == _SHORTCUT_DEFAULTS.get(action),
            }
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
        # A chord the window manager would never deliver (a bare key, a lone
        # modifier) is recorded as nothing at all, so refuse it out loud.
        if sequence and not re.search(r"\b(Ctrl|Alt)\+", sequence, re.IGNORECASE):
            return "Shortcuts need Ctrl or Alt."
        for other, bound in values.items():
            if other != action and bound == sequence and sequence:
                return ("“" + sequence + "” is already used by “"
                        + _SHORTCUT_LABELS.get(other, other) + "”.")
        values[action] = sequence
        changed = {k: v for k, v in values.items() if v != _SHORTCUT_DEFAULTS.get(k)}
        self._shortcuts_json = json.dumps(changed)
        self._notify_form_changed()
        self.shortcutsChanged.emit()
        return ""

    @Slot(str, result=str)
    def resetShortcut(self, action: str) -> str:
        # Restoring a default can itself collide: two actions whose defaults
        # were swapped. The caller shows whatever comes back.
        return self.setShortcut(action, _SHORTCUT_DEFAULTS.get(action, ""))

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
        # ``id`` exists so a page can ask for particular rows without matching
        # on their labels; the Environment card shows three of these five, and
        # yt-dlp's status belongs to Readiness while the app folder belongs to
        # the folder pickers.
        return [
            {"id": "app_folder", "label": "App folder", "value": base_dir()},
            {"id": "settings_store", "label": "Settings store", "value": self._settings.fileName()},
            {"id": "log_file", "label": "Log file", "value": os.path.join(base_dir(), "saaaveit.log")},
            {"id": "ytdlp", "label": "yt-dlp", "value": "available" if yt_dlp_available() else "not found"},
            {"id": "python", "label": "Python", "value": sys.version.split()[0]},
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
