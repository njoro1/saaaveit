@echo off
REM ================================================================
REM  Rebuild the standalone Saaaveit executable.
REM  Output: dist\Saaaveit\Saaaveit.exe  (onedir bundle)
REM
REM  Run this any time after changing Python or QML source files.
REM
REM  The build is trimmed to only the PySide6 modules the app uses
REM  (QtCore / QtGui / QtQml / QtQuick / QtQuickControls2), instead of
REM  bundling all of PySide6 (~300 modules). If you add a new Qt import
REM  to the code, add the matching hidden-import below.
REM ================================================================
setlocal
cd /d "%~dp0"

echo [1/3] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo [2/3] Removing previous build output...
if exist "dist\Saaaveit" rmdir /s /q "dist\Saaaveit"

for /f "usebackq delims=" %%P in (`python -c "import PySide6, os; print(os.path.dirname(PySide6.__file__))"`) do set PYSIDE6_DIR=%%P
if not defined PYSIDE6_DIR (
    echo ERROR: Could not locate the PySide6 package directory via python.
    pause
    exit /b 1
)
echo Found PySide6 at: %PYSIDE6_DIR%

for /f "usebackq delims=" %%F in (`python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`) do set FFMPEG_EXE=%%F
if not defined FFMPEG_EXE (
    echo ERROR: Could not locate a bundled ffmpeg binary via imageio-ffmpeg.
    echo        Install it with: python -m pip install imageio-ffmpeg
    pause
    exit /b 1
)
echo Found ffmpeg at: %FFMPEG_EXE%

echo [3/3] Building onedir bundle (trimmed PySide6 - usually under 2 min)...
REM "--hidden-import yt_dlp" pulls in yt-dlp's own PyInstaller hook (declared
REM through its "pyinstaller40" entry point), which collects the extractors,
REM requests/certifi and the yt-dlp-ejs JS helpers. A frozen build has no
REM Python interpreter to spawn, so src/ytdlp.py runs the bundled copy
REM in-process instead of shelling out to "python -m yt_dlp".
REM ffmpeg is bundled under its real name; src/media_source.py renames it to a
REM literal ffmpeg.exe at runtime, because --ffmpeg-location only finds a file
REM called ffmpeg(.exe) and without it the video+audio merge never runs.
python -m PyInstaller --noconfirm --onedir --windowed --name Saaaveit ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtQml ^
    --hidden-import PySide6.QtQuick ^
    --hidden-import PySide6.QtQuickControls2 ^
    --hidden-import PySide6.QtNetwork ^
    --hidden-import PySide6.QtWidgets ^
    --add-data "ui;ui" ^
    --add-binary "%FFMPEG_EXE%;." ^
    --add-data "ui/qml;ui/qml" ^
    --add-data "ui/qml/components;ui/qml/components" ^
    --add-data "%PYSIDE6_DIR%\qml\Qt;PySide6/qml/Qt" ^
    --add-data "%PYSIDE6_DIR%\qml\QtQml;PySide6/qml/QtQml" ^
    --add-data "%PYSIDE6_DIR%\qml\QtQuick;PySide6/qml/QtQuick" ^
    --add-data "%PYSIDE6_DIR%\qml\builtins.qmltypes;PySide6/qml" ^
    --add-data "%PYSIDE6_DIR%\qml\jsroot.qmltypes;PySide6/qml" ^
    --add-data "%PYSIDE6_DIR%\plugins\platforms;PySide6/plugins/platforms" ^
    --add-data "%PYSIDE6_DIR%\plugins\imageformats;PySide6/plugins/imageformats" ^
    --add-data "%PYSIDE6_DIR%\plugins\styles;PySide6/plugins/styles" ^
    --add-data "%PYSIDE6_DIR%\plugins\iconengines;PySide6/plugins/iconengines" ^
    --add-data "%PYSIDE6_DIR%\plugins\qmltooling;PySide6/plugins/qmltooling" ^
    --hidden-import app ^
    --hidden-import app.bridge ^
    --hidden-import app.workers ^
    --hidden-import src ^
    --hidden-import src.store ^
    --hidden-import src.media_id ^
    --hidden-import src.media_source ^
    --hidden-import src.ytdlp ^
    --hidden-import yt_dlp ^
    main.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED. See output above for details.
    pause
    exit /b 1
)

if not exist "dist\Saaaveit\Saaaveit.exe" (
    echo.
    echo BUILD FAILED: dist\Saaaveit\Saaaveit.exe was not produced.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  BUILD SUCCEEDED: dist\Saaaveit\Saaaveit.exe
echo ================================================================
pause
exit /b 0
