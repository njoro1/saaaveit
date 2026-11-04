"""One snapshot per queued download, run strictly one at a time.

A job captures everything a download needs *at enqueue time*. Nothing in here
reads the live form: with a queue the user keeps editing the form while earlier
jobs are still waiting, so a job that resolved its own format, title or output
path at completion time would download the wrong stream and file itself in the
library under whatever was inspected last.

Jobs run one at a time on purpose, not as a simplification. yt-dlp is not
re-entrant: in a frozen build ``src.ytdlp._run_inprocess`` swaps the
process-global ``sys.stdout``/``sys.stderr`` for the duration of the run, so two
downloads in flight would serialise on ``_INPROC_LOCK`` anyway while
interleaving their output into each other's stream.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

TERMINAL = (DONE, FAILED, CANCELLED)

_STATE_LABEL = {
    QUEUED: "Waiting",
    RUNNING: "Downloading",
    DONE: "Saved",
    FAILED: "Failed",
    CANCELLED: "Cancelled",
}


@dataclass
class QueueJob:
    """A download the user committed to, plus whatever it has produced so far."""

    id: int
    url: str
    # ``video`` fetches the stream and, when asked, its subtitle; ``subtitle``
    # is the "fetch subtitle only" leg, for a video already on disk.
    kind: str = "video"
    video_id: str = ""
    title: str = ""
    thumbnail: str = ""
    duration: int = 0
    codec: str = "best"
    resolution: str = "best"
    format_selector: str = ""
    format_label: str = ""
    expect: dict = field(default_factory=dict)
    out_base: str = ""
    download_dir: str = ""
    subtitle_lang: str = ""
    subtitle_kind: str = ""
    subtitle_label: str = ""
    subtitle_leg_wanted: bool = False

    state: str = QUEUED
    progress: int = 0
    stage: str = ""
    video_outcome: str = ""
    subtitle_outcome: str = ""
    # The legs still in flight for this job. Per-job rather than per-bridge:
    # the video leg chains the subtitle leg, and the answer must belong to the
    # job that is running, not to whatever is next in line.
    pending_legs: list = field(default_factory=list)
    saved_video: str = ""
    saved_subtitle: str = ""
    error: str = ""
    notice: str = ""
    status: str = ""

    # -------------------------------------------------------------- derived
    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL

    @property
    def state_label(self) -> str:
        return _STATE_LABEL.get(self.state, self.state)

    @property
    def name(self) -> str:
        """What to call this job when the title is missing."""
        return self.title or os.path.basename(self.url) or self.video_id

    @property
    def outcome(self) -> str:
        """One word for the whole job, from the two independent legs.

        A cancelled video leg with a saved subtitle is still a partial success,
        so the job reports the best leg that happened rather than the worst.
        """
        legs = (self.video_outcome, self.subtitle_outcome)
        if self.state == CANCELLED or CANCELLED in legs:
            return CANCELLED if "ok" not in legs else DONE
        if "ok" in legs:
            return DONE
        if FAILED in legs:
            return FAILED
        return self.state

    def duplicate_key(self) -> tuple:
        """Identity for repeat detection: same video, same stream, same track."""
        return (self.video_id or self.url, self.format_selector, self.subtitle_lang)

    @property
    def summary(self) -> str:
        """The format and track line shown under the job's title."""
        parts = [p for p in (self.format_label, self.subtitle_label) if p]
        return " · ".join(parts) if parts else ""

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "kind": self.kind,
            "videoId": self.video_id,
            "title": self.title,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "codec": self.codec,
            "resolution": str(self.resolution),
            "formatSelector": self.format_selector,
            "formatLabel": self.format_label,
            "expect": dict(self.expect or {}),
            "outBase": self.out_base,
            "downloadDir": self.download_dir,
            "subtitleLang": self.subtitle_lang,
            "subtitleKind": self.subtitle_kind,
            "subtitleLabel": self.subtitle_label,
            "subtitleLegWanted": bool(self.subtitle_leg_wanted),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "QueueJob":
        """Rebuild a job, tolerating a store written by an older build.

        A restored job is always ``queued``: nothing survives a restart already
        half-written, and nothing may start by itself.
        """
        return cls(
            id=int(raw.get("id") or 0),
            url=str(raw.get("url") or ""),
            kind=str(raw.get("kind") or "video"),
            video_id=str(raw.get("videoId") or ""),
            title=str(raw.get("title") or ""),
            thumbnail=str(raw.get("thumbnail") or ""),
            duration=int(raw.get("duration") or 0),
            codec=str(raw.get("codec") or "best"),
            resolution=str(raw.get("resolution") or "best"),
            format_selector=str(raw.get("formatSelector") or ""),
            format_label=str(raw.get("formatLabel") or ""),
            expect=dict(raw.get("expect") or {}),
            out_base=str(raw.get("outBase") or ""),
            download_dir=str(raw.get("downloadDir") or ""),
            subtitle_lang=str(raw.get("subtitleLang") or ""),
            subtitle_kind=str(raw.get("subtitleKind") or ""),
            subtitle_label=str(raw.get("subtitleLabel") or ""),
            subtitle_leg_wanted=bool(raw.get("subtitleLegWanted")),
        )
