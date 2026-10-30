"""Thumbnails must be cached locally, cheaply and without ever raising.

QML in the frozen build cannot load remote images, so ``cache_thumbnail`` is the
only path from the inspection payload to something the UI can render. A failure
here is decorative, never fatal: every branch returns ``""``.
"""
from __future__ import annotations

import os
import urllib.request

import pytest
from PySide6.QtCore import QUrl

from app import thumbnail


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


def test_downloads_and_returns_a_local_file_url(tmp_path, monkeypatch):
    seen = _calls(monkeypatch, _Response(b"\xff\xd8jpeg-bytes", length=11))
    url = thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    assert seen == ["https://img.example/t.jpg"]
    path = os.path.join(str(tmp_path), "thumbs", "abc123.jpg")
    assert url == QUrl.fromLocalFile(path).toString()
    assert url.startswith("file:///")
    with open(path, "rb") as handle:
        assert handle.read() == b"\xff\xd8jpeg-bytes"


def test_a_cache_hit_never_touches_the_network(tmp_path, monkeypatch):
    directory = os.path.join(str(tmp_path), "thumbs")
    os.makedirs(directory)
    path = os.path.join(directory, "abc123.jpg")
    with open(path, "wb") as handle:
        handle.write(b"cached")

    seen = _calls(monkeypatch, _Response(b"fresh"))
    url = thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path))

    assert seen == []
    assert url == QUrl.fromLocalFile(path).toString()


def test_the_video_id_is_sanitised_for_the_cache_filename(tmp_path, monkeypatch):
    _calls(monkeypatch, _Response(b"data"))
    thumbnail.cache_thumbnail("../../evil/id", "https://img.example/t.jpg", str(tmp_path))

    assert os.listdir(os.path.join(str(tmp_path), "thumbs")) == ["______evil_id.jpg"]


def test_an_empty_video_id_is_refused(tmp_path, monkeypatch):
    seen = _calls(monkeypatch, _Response(b"data"))
    assert thumbnail.cache_thumbnail("   ", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert seen == []


def test_a_missing_remote_url_is_refused(tmp_path, monkeypatch):
    seen = _calls(monkeypatch, _Response(b"data"))
    assert thumbnail.cache_thumbnail("abc123", "", str(tmp_path)) == ""
    assert seen == []


def test_a_declared_oversized_thumbnail_is_rejected_without_downloading(tmp_path, monkeypatch):
    response = _Response(b"\xff" * 32, length=6 * 1024 * 1024)
    _calls(monkeypatch, response)
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(os.path.join(str(tmp_path), "thumbs", "abc123.jpg"))


def test_an_oversized_body_is_rejected_without_a_content_length(tmp_path, monkeypatch):
    too_big = thumbnail._MAX_BYTES + 1
    _calls(monkeypatch, _Response(b"x" * too_big))
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(os.path.join(str(tmp_path), "thumbs", "abc123.jpg"))


def test_a_network_failure_is_silent(tmp_path, monkeypatch):
    _calls(monkeypatch, error=OSError("connection reset"))
    assert thumbnail.cache_thumbnail("abc123", "https://img.example/t.jpg", str(tmp_path)) == ""
    assert not os.path.exists(os.path.join(str(tmp_path), "thumbs", "abc123.jpg"))
