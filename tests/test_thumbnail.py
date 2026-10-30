"""Thumbnails must be cached locally, cheaply and without ever raising.

QML in the frozen build cannot load remote images, so ``cache_thumbnail`` is the
only path from the inspection payload to something the UI can render. A failure
here is decorative, never fatal: every branch returns ``""``.

The cached file is also the place where the image is cropped to 16:9 and given
rounded corners (QML's ``clip`` is rectangular).
"""
from __future__ import annotations

import os
import urllib.request

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QUrl
from PySide6.QtGui import QColor, QImage

from app import thumbnail


def _png(width: int = 64, height: int = 36, color: str = "#3366cc") -> bytes:
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    assert buffer.open(QIODevice.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data())


class _Response:
    def __init__(self, data: bytes, length: int | None = None) -> None:
        self._data = data
        self.headers = {} if length is None else {"Content-Length": str(length)}

    def read(self, size: int = -1) -> bytes:
        return self._data if size < 0 else self._data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _calls(monkeypatch, response=None, error=None) -> list[str]:
    seen: list[str] = []

    def fake_urlopen(url, timeout=None):
        seen.append(url)
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return seen


def _cached(tmp_path, video_id: str = "abc123") -> str:
    return os.path.join(str(tmp_path), "thumbs", video_id + ".png")


def test_downloads_and_returns_a_local_file_url(tmp_path, monkeypatch):
    payload = _png()
    seen = _calls(monkeypatch, _Response(payload, length=len(payload)))
    url = thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    assert seen == ["https://img.example/t.jpg"]
    path = _cached(tmp_path)
    assert url == QUrl.fromLocalFile(path).toString()
    assert url.startswith("file:///")
    image = QImage(path)
    assert not image.isNull()
    assert (image.width(), image.height()) == (64, 36)


def test_downloaded_images_are_cropped_to_sixteen_by_nine(tmp_path, monkeypatch):
    payload = _png(40, 30)  # 4:3, like YouTube's letterboxed hqdefault
    _calls(monkeypatch, _Response(payload))
    thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    image = QImage(_cached(tmp_path))
    assert (image.width(), image.height()) == (40, 22)


def test_large_images_are_downscaled(tmp_path, monkeypatch):
    _calls(monkeypatch, _Response(_png(1280, 720)))
    thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    image = QImage(_cached(tmp_path))
    assert (image.width(), image.height()) == (640, 360)


def test_corners_are_transparent_and_the_centre_is_opaque(tmp_path, monkeypatch):
    _calls(monkeypatch, _Response(_png()))
    thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    image = QImage(_cached(tmp_path))
    # Antialiasing leaves a sliver of coverage in the very corner pixel.
    assert image.pixelColor(0, 0).alpha() < 64
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 255


def test_a_cache_hit_never_touches_the_network(tmp_path, monkeypatch):
    directory = os.path.join(str(tmp_path), "thumbs")
    os.makedirs(directory)
    path = _cached(tmp_path)
    with open(path, "wb") as handle:
        handle.write(_png())

    seen = _calls(monkeypatch, _Response(_png()))
    url = thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    assert seen == []
    assert url == QUrl.fromLocalFile(path).toString()


def test_the_video_id_is_sanitised_for_the_cache_filename(tmp_path, monkeypatch):
    _calls(monkeypatch, _Response(_png()))
    thumbnail.cache_thumbnail("../../evil/id", "https://img.example/t.jpg", str(tmp_path))

    assert os.listdir(os.path.join(str(tmp_path), "thumbs")) == ["______evil_id.png"]


def test_an_empty_video_id_is_refused(tmp_path, monkeypatch):
    seen = _calls(monkeypatch, _Response(_png()))
    assert thumbnail.cache_thumbnail("   ", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert seen == []


def test_a_missing_remote_url_is_refused(tmp_path, monkeypatch):
    seen = _calls(monkeypatch, _Response(_png()))
    assert thumbnail.cache_thumbnail("abc123", "", str(tmp_path)) == ""
    assert seen == []


def test_a_declared_oversized_thumbnail_is_rejected_without_downloading(tmp_path, monkeypatch):
    response = _Response(_png(), length=6 * 1024 * 1024)
    _calls(monkeypatch, response)
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(_cached(tmp_path))


def test_an_oversized_body_is_rejected_without_a_content_length(tmp_path, monkeypatch):
    too_big = thumbnail._MAX_BYTES + 1
    _calls(monkeypatch, _Response(b"x" * too_big))
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(_cached(tmp_path))


def test_an_undecodable_image_is_silent(tmp_path, monkeypatch):
    _calls(monkeypatch, _Response(b"not an image"))
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(_cached(tmp_path))


def test_a_network_failure_is_silent(tmp_path, monkeypatch):
    _calls(monkeypatch, error=OSError("connection reset"))
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(_cached(tmp_path))
