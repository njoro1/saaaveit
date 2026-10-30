import sys, traceback, time
sys.path.insert(0, '.')
from PySide6.QtGui import QGuiApplication
app = QGuiApplication([])
from app.bridge import DownloaderBridge
try:
    b = DownloaderBridge()
    b.url = 'https://youtu.be/dQw4w9WgXcQ'
    time.sleep(8)
except Exception:
    traceback.print_exc()
print("FINISHED")
