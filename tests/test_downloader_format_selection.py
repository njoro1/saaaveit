"""QML-level regression: a pick in the format matrix must reach the bridge.

Historical bug — and the reason the download ignored the pickers entirely:
a selection property declared as ``@Property(object)`` is registered by PySide6
with the type ``PySide::PyObjectWrapper``. The QML engine *refuses to write*
that type ("Cannot assign int to PySide::PyObjectWrapper"), so every resolution
pick was silently discarded. The bridge kept its default ("best"), which
resolves to the highest-quality stream — while the UI happily showed the
resolution the user had just chosen.

The dropdowns are gone; the matrix replaced them, and the write path now runs
through ``appBridge.pickFormat(codec, resolution)`` — one slot, both halves, so
the setter-order trap that pair used to have cannot come back. These tests
still drive the *real QML items* (cell click -> signal -> slot) so the whole
chain is exercised, not just the logic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtQuick import QQuickItem

from src import media_source

QML_DIR = Path(__file__).resolve().parent.parent / "ui" / "qml"


def _formats() -> list[dict]:
    """h264: 1080/720/480/360 (360 muxed) · vp9: 2160/720 · av1: 2160."""
    def fmt(fid, ext, height, vcodec, acodec, tbr, size):
        return {"format_id": fid, "ext": ext, "height": height,
                "vcodec": vcodec, "acodec": acodec, "tbr": tbr,
                "filesize": size, "fps": 30}

    return [
        fmt("140", "m4a", None, "none", "mp4a.40.2", 128, 4_000_000),
        fmt("401", "mp4", 2160, "av01.0.13M.10", "none", 10000, 120_000_000),
        fmt("315", "webm", 2160, "vp9", "none", 12000, 150_000_000),
        fmt("302", "webm", 720, "vp9", "none", 1800, 15_000_000),
        fmt("137", "mp4", 1080, "avc1.640028", "none", 4500, 40_000_000),
        fmt("136", "mp4", 720, "avc1.4d401f", "none", 2500, 20_000_000),
        fmt("135", "mp4", 480, "avc1.4d401e", "none", 1200, 9_000_000),
        fmt("134", "mp4", 360, "avc1.4d401e", "none", 650, 5_000_000),
        fmt("18", "mp4", 360, "avc1.42001E", "mp4a.40.2", 700, 6_000_000),
    ]


@pytest.fixture(scope="module")
def session(qml_main):
    """Reuse the session-wide Main.qml instance (see ``conftest.qml_main``)."""
    bridge = qml_main.bridge
    root = qml_main.root
    warnings = qml_main.warnings
    bridge._info_gen += 1
    _codecs, _res, matrix, best = media_source._build_matrix(_formats())
    bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps({
        "title": "Test video",
        "video_id": "test0000001",
        "language": "en",
        "codecs": _codecs,
        "resolutions": _res,
        "matrix": matrix,
        "best": best,
        "codecs_available": {"av1": True, "vp9": True, "h264": True},
        "subtitle_tracks": [
            {"code": "en", "name": "English", "kind": "manual",
             "label": "English · manual", "isOriginal": True},
        ],
        "default_subtitle_track": "en",
    }))
    yield bridge, root, warnings


def _cells_by_name(root) -> dict:
    """objectName -> item for every cell the grid has instantiated.

    ``Repeater`` delegates are not in the window's QObject child list, so
    ``findChild`` cannot reach ``download.formatRow.*`` — the walk has to go
    through ``childItems()`` from the window's content item.
    """
    found: dict[str, QQuickItem] = {}

    def walk(node) -> None:
        for child in node.childItems():
            name = child.objectName()
            if name.startswith("download.formatRow."):
                found[name] = child
            walk(child)

    walk(root.contentItem())
    return found


def _cell(bridge, root, codec: str, resolution) -> QQuickItem:
    """The matrix cell for a pair, found through the same model it renders.

    Cells carry ``download.formatRow.<index>`` where index is the entry's
    position in ``formatRows``, so the test resolves pair -> index exactly the
    way the grid does instead of hard-coding a slot layout. Pairs that are not
    offered have no cell at all, which is itself an assertion below.
    """
    cells = _cells_by_name(root)
    rows = bridge.formatRows
    for index, row in enumerate(rows):
        if row["isBest"]:
            continue
        if row["codec"] == codec and str(row["resolution"]) == str(resolution):
            item = cells.get(f"download.formatRow.{index}")
            assert item is not None, f"formatRow.{index} missing from the grid"
            return item
    raise AssertionError(f"no matrix cell for {codec}/{resolution}")


def _press(button: QQuickItem) -> None:
    """Activate a real QML button the way a click would."""
    assert QMetaObject.invokeMethod(button, "click", Qt.DirectConnection)


@pytest.fixture()
def panel(session):
    bridge, root, warnings = session
    assert root.findChild(QQuickItem, "download.bestCell") is not None, (
        "download.bestCell not found")
    # Back to the default state so the tests do not depend on each other.
    bridge.pickFormat(bridge.codecs[0]["id"], "best")
    warnings.clear()
    return bridge, root, warnings


class TestMatrixPicksReachTheBridge:
    def test_cell_click_is_stored(self, panel):
        bridge, root, warnings = panel
        _press(_cell(bridge, root, "h264", "360"))
        assert bridge.selectedCodec == "h264"
        assert str(bridge.selectedResolution) == "360", (
            "resolution pick was dropped; warnings: " + "; ".join(warnings))
        assert not [w for w in warnings if "Cannot assign" in w], warnings

    def test_cell_click_changes_the_download_selector(self, panel):
        """End to end: pressing the H.264 360p cell must select the real 360p
        stream, not the highest-quality one the video happens to serve."""
        bridge, root, _warnings = panel
        _press(_cell(bridge, root, "h264", "360"))

        selector = bridge._selector()
        assert selector == "18", selector
        assert bridge.selectedOption["resolution"] == 360
        # The default (av1 @ best) would have been the 2160p stream.
        assert "401" not in selector

    def test_best_cell_picks_the_escape_hatch(self, panel):
        bridge, root, _warnings = panel
        _press(_cell(bridge, root, "h264", "360"))
        _press(root.findChild(QQuickItem, "download.bestCell"))
        assert bridge.selectedCodec == "best"
        assert str(bridge.selectedResolution) == "best"
        assert bridge._selector() != ""

    def test_cells_are_the_only_offered_pairs(self, panel):
        """h264 serves no 2160p - and the grid must not show a cell for it."""
        bridge, root, _warnings = panel
        with pytest.raises(AssertionError, match="no matrix cell"):
            _cell(bridge, root, "h264", "2160")


class TestCellsMirrorTheStore:
    """The pressed cell is derived from ``formatRows[*].selected``.

    That flag is the store's own, so any change underneath the grid - an
    external ``pickFormat``, a codec reset, a re-inspect - has to repaint the
    grid, not leave it showing a stale press.
    """

    def test_the_pressed_cell_follows_an_external_pick(self, panel):
        bridge, root, _warnings = panel
        _press(_cell(bridge, root, "h264", "360"))

        bridge.pickFormat("vp9", "720")

        pressed = [r for r in bridge.formatRows if r["selected"]]
        assert len(pressed) == 1
        assert pressed[0]["codec"] == "vp9"
        assert str(pressed[0]["resolution"]) == "720"

    def test_codec_that_cannot_serve_the_row_resets_to_best(self, panel):
        bridge, root, _warnings = panel
        _press(_cell(bridge, root, "h264", "1080"))
        assert str(bridge.selectedResolution) == "1080"

        # vp9 tops out below 1080p on this video: pickFormat normalises.
        bridge.pickFormat("vp9", "1080")
        assert str(bridge.selectedResolution) == "best"
        assert bridge.selectedOption.get("format_selector")


class TestUnavailablePairIsReported:
    def test_unavailable_resolution_has_no_selector(self, panel):
        """h264 serves no 2160p: the option must be empty so the download can
        refuse, instead of falling back to a "best" stream. The grid cannot
        offer this pair, so the store is driven directly - the guard still has
        to refuse."""
        bridge, _root, _warnings = panel
        bridge.selectedCodec = "h264"
        bridge.selectedResolution = "2160"

        assert bridge.selectedOption == {}
        assert bridge._selector() == ""
        assert "2160p" in bridge.selectionError
        assert "1080p" in bridge.selectionError

    def test_download_button_is_disabled_without_a_selection(self, panel):
        bridge, root, _warnings = panel
        bridge.selectedCodec = "h264"
        bridge.selectedResolution = "2160"
        button = root.findChild(QQuickItem, "download.downloadButton")
        assert button is not None, "download.downloadButton not found"
        assert bridge.canDownload is False


SELECTION_ERROR = "download.selectionError"
SUMMARY_VIDEO = "download.summaryVideo"


class TestSelectionLabelsExplainUnavailablePairs:
    """The panel must *say* what is wrong, not just refuse silently."""

    @pytest.fixture()
    def labeled(self, session):
        bridge, root, warnings = session
        error = root.findChild(QQuickItem, SELECTION_ERROR)
        assert error is not None, f"{SELECTION_ERROR} not found"
        bridge.pickFormat(bridge.codecs[0]["id"], "best")
        warnings.clear()
        return bridge, root, error, warnings

    def test_available_pair_shows_no_error(self, labeled):
        bridge, root, error, _warnings = labeled
        _press(_cell(bridge, root, "h264", "360"))
        assert str(error.property("text")) == ""

    def test_unavailable_pair_names_the_missing_format(self, labeled):
        bridge, _root, error, _warnings = labeled
        bridge.selectedCodec = "h264"
        bridge.selectedResolution = "2160"  # h264 tops out at 1080p
        text = str(error.property("text"))
        assert "not available" in text.lower(), text
        assert "H.264" in text and "2160p" in text, text
        # and it must tell the user what they *can* pick
        assert "1080p" in text, text

    def test_recovers_when_the_pick_becomes_valid(self, labeled):
        bridge, root, error, _warnings = labeled
        bridge.selectedCodec = "h264"
        bridge.selectedResolution = "2160"
        assert "not available" in str(error.property("text")).lower()
        _press(_cell(bridge, root, "h264", "1080"))
        assert str(error.property("text")) == ""

    def test_the_summary_reports_the_pressed_cell(self, labeled):
        bridge, root, _error, _warnings = labeled
        video = root.findChild(QQuickItem, SUMMARY_VIDEO)
        assert video is not None, f"{SUMMARY_VIDEO} not found"
        _press(_cell(bridge, root, "av1", "2160"))
        text = str(video.property("text"))
        assert "2160" in text, text
