#!/usr/bin/env python3
"""GUI entry point for the Saaaveit."""
from __future__ import annotations

import os
import sys

# Running ``python main.py`` must put this folder on sys.path so ``app`` and
# ``src`` resolve without an install step.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from app.bridge import DownloaderBridge, base_dir, setup_logging  # noqa: E402


def _resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", base_dir())
    return os.path.join(base, *parts)


def _resolve_qml_dirs(frozen_base: str | None):
    """Return (qml_dir, plugins_dir) for the PySide6 installation."""
    if frozen_base:
        candidate_qml = os.path.join(frozen_base, "PySide6", "qml")
        candidate_plugins = os.path.join(frozen_base, "PySide6", "plugins")
        if os.path.isdir(candidate_qml):
            return candidate_qml, candidate_plugins
        return os.path.join(frozen_base, "ui", "qml"), candidate_plugins
    try:
        import PySide6

        pyside6 = os.path.dirname(PySide6.__file__)
    except Exception:  # noqa: BLE001
        pyside6 = ""
    return (
        os.path.join(pyside6, "qml") if pyside6 else "",
        os.path.join(pyside6, "plugins") if pyside6 else "",
    )


def _initial_url(argv: list[str]) -> str:
    """The first argument that looks like a URL, if any."""
    for value in argv[1:]:
        text = value.strip()
        if text.startswith(("http://", "https://", "www.")):
            return text
    return ""


def _pin_style() -> None:
    """Force the Basic controls style, ignoring the environment.

    Every custom component in ``ui/qml/components`` replaces ``background`` or
    ``contentItem``. The native Windows and Fusion styles silently refuse those
    overrides, so an inherited ``QT_QUICK_CONTROLS_STYLE`` from the shell would
    change how the entire app renders. ``setdefault`` is not enough here.
    """
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"


def main() -> int:
    _pin_style()

    logger = setup_logging(base_dir())
    logger.info(
        "Starting Saaaveit | base_dir=%s | frozen=%s | python=%s",
        base_dir(),
        getattr(sys, "frozen", False),
        sys.version.split()[0],
    )

    def _excepthook(exc_type, exc_value, traceback) -> None:
        logger.exception("Unhandled exception", exc_info=(exc_type, exc_value, traceback))

    sys.excepthook = _excepthook

    qml_dir, plugins_dir = _resolve_qml_dirs(getattr(sys, "_MEIPASS", None))
    if os.path.isdir(plugins_dir) and "QT_PLUGIN_PATH" not in os.environ:
        os.environ["QT_PLUGIN_PATH"] = plugins_dir

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Saaaveit")
    app.setOrganizationName("Njoro")

    engine = QQmlApplicationEngine()
    if os.path.isdir(qml_dir):
        engine.addImportPath(qml_dir)

    warnings: list[str] = []
    engine.warnings.connect(lambda msgs: warnings.extend(str(m) for m in msgs))

    bridge = DownloaderBridge()
    url = _initial_url(sys.argv)
    if url:
        bridge.url = url
    engine.rootContext().setContextProperty("appBridge", bridge)

    qml_file = _resource_path("ui", "qml", "Main.qml")
    engine.load(QUrl.fromLocalFile(os.path.abspath(qml_file)))

    if not engine.rootObjects():
        logger.error("QML failed to load: %s", qml_file)
        for warning in warnings:
            logger.error("QML warning: %s", warning)
        return -1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
