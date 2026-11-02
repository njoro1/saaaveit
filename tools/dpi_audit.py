"""T7.3 audit: render every page at a given scale factor and window size."""
import json
import os
import sys
import tempfile
from pathlib import Path

scale = sys.argv[1] if len(sys.argv) > 1 else "1.0"
width = int(sys.argv[2]) if len(sys.argv) > 2 else 1240
height = int(sys.argv[3]) if len(sys.argv) > 3 else 820
os.environ["QT_SCALE_FACTOR"] = scale

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401

from src import store  # noqa: E402

_S = QSettings(str(Path(tempfile.mkdtemp(prefix="saaaveit-dpi-")) / "s.ini"), QSettings.IniFormat)
_S.clear()
_S.sync()
store.settings = lambda: _S

from app.bridge import DownloaderBridge, register_bundled_fonts  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from screenshot import QML_DIR, _payload, _seed_history, _settle  # noqa: E402

OUT = ROOT / "shots" / "t7" / f"{scale}x-{width}x{height}"
OUT.mkdir(parents=True, exist_ok=True)

app = QGuiApplication([])
register_bundled_fonts()
engine = QQmlApplicationEngine()
engine.addImportPath(str(QML_DIR))
bridge = DownloaderBridge()
bridge._url = "https://example.com/video?v=dQw4w9WgXcQ"
bridge._info_gen += 1
bridge._on_info_done(f"INFO:{bridge._info_gen}|" + json.dumps(_payload()))
_seed_history(bridge)
engine.rootContext().setContextProperty("appBridge", bridge)
warnings = []
engine.warnings.connect(lambda msgs: warnings.extend(str(m) for m in msgs))
engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
root = engine.rootObjects()[0]
root.setProperty("width", width)
root.setProperty("height", height)
root.show()
_settle(app)

for page in (0, 1, 2):
    root.setProperty("currentPage", page)
    for theme in ("dark", "light"):
        bridge._theme_name = theme
        bridge.themeChanged.emit()
        _settle(app)
        img = root.grabWindow()
        img.save(str(OUT / f"page{page}-{theme}.png"))
        print(f"{scale}x {width}x{height} page{page} {theme} -> {img.width()}x{img.height()}")
print("warnings:", warnings)
