"""Background workers for inspection and downloads.

Every worker reports its result with a *generation token* echoed in the payload.
The bridge compares the token against the current one and drops stale results —
``sender()`` identifies the signals object, never the ``QRunnable``, so an
identity check cannot work.
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src import media_source

from app.thumbnail import cache_thumbnail


class InfoSignal(QObject):
    done = Signal(str)


class DownloadSignal(QObject):
    progress = Signal(str)
    percent = Signal(int)
    done = Signal(str)


class InfoWorker(QRunnable):
    """Inspects a URL for available formats and subtitle tracks."""

    def __init__(self, url: str, token: int = 0) -> None:
        super().__init__()
        self.url = url
        self.token = token
        self.signals = InfoSignal()

    @Slot()
    def run(self) -> None:
        try:
            info = media_source.inspect_video(self.url)
            # QML cannot load remote images in the frozen build, so hand it a
            # cached local file instead ("" when the fetch fails).
            info["thumbnail"] = cache_thumbnail(
                str(info.get("video_id") or ""), str(info.get("thumbnail") or "")
            )
            self.signals.done.emit(f"INFO:{self.token}|" + json.dumps(info))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.signals.done.emit(f"INFOERROR:{self.token}|{exc}")


class DownloadWorker(QRunnable):
    """Downloads the video, one subtitle track, or both legs of one operation.

    ``kind`` is ``"video"`` or ``"subtitle"``. The worker owns its yt-dlp
    process handle so the bridge can cancel it from the UI thread.
    """

    def __init__(
        self,
        kind: str,
        url: str,
        *,
        format_selector: str = "",
        out_template: str = "",
        token: int = 0,
        expect: dict | None = None,
        subtitle_lang: str = "",
        subtitle_kind: str = "",
    ) -> None:
        super().__init__()
        self.kind = kind
        self.url = url
        self.format_selector = format_selector
        self.out_template = out_template
        self.token = token
        self.expect = expect or None
        self.subtitle_lang = subtitle_lang
        self.subtitle_kind = subtitle_kind
        self.proc_ref: dict = {}
        self.canceled = False
        self.signals = DownloadSignal()

    def cancel(self) -> None:
        self.canceled = True
        proc = self.proc_ref.get("proc")
        if proc is not None:
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    def _verify(self, path: str) -> str:
        """Warn (never fail) when the file differs from the requested format."""
        expect = self.expect
        if not expect or not path:
            return ""
        probe = media_source.probe_video_file(path)
        if not probe:
            return ""
        want_codec = (expect.get("codec") or "").strip().lower()
        want_height = int(expect.get("height") or 0)
        got_codec = (probe.get("codec") or "").strip().lower()
        got_height = int(probe.get("height") or 0)
        any_codec = bool(expect.get("cap")) or want_codec in ("", "best")

        problems = []
        if want_codec and got_codec and not any_codec and want_codec != got_codec:
            problems.append(
                f"codec {media_source._CODEC_LABEL.get(got_codec, got_codec)}"
                f" instead of {media_source._CODEC_LABEL.get(want_codec, want_codec)}"
            )
        if want_height and got_height:
            if expect.get("cap"):
                if got_height > want_height:
                    problems.append(f"{got_height}p instead of \u2264 {want_height}p")
            elif got_height != want_height:
                problems.append(f"{got_height}p instead of {want_height}p")
        if not problems:
            return ""
        return (
            "[warn] The downloaded file is "
            + " and ".join(problems)
            + ". The upstream service sometimes re-maps a stream; re-run the download "
              "or pick another resolution if this is not what you wanted."
        )

    @Slot()
    def run(self) -> None:
        try:
            if self.kind == "video":
                path = media_source.download_video(
                    self.url,
                    self.format_selector,
                    self.out_template,
                    progress_cb=lambda line: self.signals.progress.emit(line + "\n"),
                    percent_cb=self.signals.percent.emit,
                    proc_ref=self.proc_ref,
                    cancel_check=lambda: self.canceled,
                )
                warning = self._verify(path)
                if warning:
                    self.signals.progress.emit(warning + "\n")
            else:
                path = media_source.download_subtitle(
                    self.url,
                    self.subtitle_lang,
                    self.out_template,
                    progress_cb=lambda line: self.signals.progress.emit(line + "\n"),
                    proc_ref=self.proc_ref,
                    cancel_check=lambda: self.canceled,
                    kind=self.subtitle_kind,
                )
            self.signals.done.emit(f"DONE:{self.token}|{self.kind}:{path}")
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            if self.canceled:
                self.signals.done.emit(f"CANCEL:{self.token}|{self.kind}")
            else:
                self.signals.done.emit(f"ERROR:{self.token}|{self.kind}:{exc}")
