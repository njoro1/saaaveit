"""Shared fixtures for the downloader's test suite."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The offscreen platform starts with an empty font database unless it is told
# where system fonts live; without this, font resolution falls back arbitrarily.
os.environ.setdefault(
    "QT_QPA_FONTDIR",
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
)
# Must match main.py: our controls replace `background` / `contentItem`, which
# the native Windows style refuses (and then silently ignores them).
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QSettings, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

# The app's settings are read from the real user store in production. The suite
# must never read or write that store: redirect QSettings to a throwaway INI
# directory before any bridge is constructed.
_SETTINGS_DIR = tempfile.mkdtemp(prefix="saaaveit-settings-")
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _SETTINGS_DIR)
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, _SETTINGS_DIR)

from app.bridge import DownloaderBridge, register_bundled_fonts  # noqa: E402
from src import store  # noqa: E402

QML_DIR = ROOT / "ui" / "qml"


@pytest.fixture(scope="session", autouse=True)
def gui_app():
    if QGuiApplication.instance() is None:
        app = QGuiApplication([])
    else:
        app = QGuiApplication.instance()
    # Same font database the shipped app builds, so the suite measures the
    # metrics users will actually see (Theme falls back if this no-ops).
    register_bundled_fonts()
    yield app


@pytest.fixture()
def clean_settings(monkeypatch, tmp_path):
    """Give every bridge a settings file private to this test."""
    settings_file = tmp_path / "settings.ini"
    handle = QSettings(str(settings_file), QSettings.IniFormat)
    handle.clear()
    handle.sync()
    monkeypatch.setattr(store, "settings", lambda: handle)
    return handle


@pytest.fixture()
def bridge(gui_app, clean_settings):
    return DownloaderBridge()


@pytest.fixture(scope="session")
def qml_main(gui_app):
    """``Main.qml`` loaded exactly once for the whole session.

    Creating a second ``QQmlApplicationEngine`` and loading ``Main.qml`` again
    can crash the process: an engine's ``deleteLater()`` is only processed while
    an event loop runs, which offscreen pytest never does. Every QML test
    therefore shares this one instance, and resets the bridge's state itself.
    """
    bridge = DownloaderBridge()
    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda errs: warnings.extend(e.toString() for e in errs))
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("appBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("Main.qml failed to load: " + "\n".join(warnings))
    # A rejected binding still loads, and the ``ui`` fixture clears the list per
    # module, so a warning produced here would never be read by any test.
    if warnings:
        raise RuntimeError("Main.qml loaded with QML warnings: " + "\n".join(warnings))
    yield SimpleNamespace(
        bridge=bridge,
        engine=engine,
        root=engine.rootObjects()[0],
        warnings=warnings,
    )
