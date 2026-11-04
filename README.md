# Saaaveit

A small, standalone desktop app for Windows that downloads a video **and**, in
the same action, one of the subtitle tracks the video offers — plus a
command-line mode for the same engine.

It is a personal project, not a service: everything runs on your machine,
there is no account, no telemetry and no network endpoint beyond the video
service itself. Settings and download history live in a local `QSettings`
store. It shares no code, configuration or process with any other
application.

## What it does

1. Paste a video URL and press **Inspect**. The app reads the formats the
   service actually serves — AV1, VP9 and H.264 at every available resolution —
   plus every subtitle track (manual and auto-generated, in every language).
2. Pick a codec and resolution. The matrix and the dropdowns always agree.
3. Pick a subtitle track, or leave it on **None — video only**. By default
   nothing is preselected; if you want a track chosen for you on every
   inspection, set **Settings → Default subtitle**.
4. Press **Download**. The video is fetched first, then the subtitle. If the
   video leg fails, the subtitle leg still runs — each leg reports its own
   outcome.
5. Queue as many as you like. While a job runs the form stays usable, the
   primary button reads **Add to queue**, and each job keeps the picks it was
   committed with. Downloads run strictly one at a time, in order; a failed job
   reports its reason on its own row and the batch carries on. The queue is
   saved and comes back stopped, so nothing starts by itself after a restart.

**Fetch subtitle only** is there for the case where you already have the video.

## How it is built

| Layer | Choice |
| --- | --- |
| UI | PySide6 + QML, fully custom controls (no native widgets) |
| Engine | `yt-dlp` (pip-installed, or a binary next to the .exe when frozen) |
| Bridge | `app/bridge.py` — one Qt object exposing inspection, downloads, queue, library and settings to QML |
| Theming | One design-token singleton (`ui/qml/Theme.qml`): dark/light, six accent hues (Cobalt is the brand default), comfortable density, reduced motion. Colour pairs are held against WCAG floors by `tests/test_theme_contrast.py`. |
| Input | Every action has a keyboard shortcut; `Ctrl+K` opens a command palette. |

## Requirements

* Python 3.10+
* `pip install -r requirements.txt`
* `ffmpeg` — `imageio-ffmpeg` provides one; alternatively put `ffmpeg.exe` on
  `PATH`. Without it, separate video and audio streams cannot be merged.
* For the test suite: `pip install -r requirements-dev.txt`

## Run

```
python main.py
```

A URL may be passed on the command line and will be inspected on startup:

```
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Command line

The CLI uses the same engine as the GUI:

```
python cli.py --list-formats URL
python cli.py URL --codec vp9 --resolution 1080 --subs ja
python cli.py URL --subs-only --subs ja -o C:\Downloads
```

Run `python cli.py --help` for the full flag list (`--json`, `--subs-kind`,
`--filename-template`, …).

## Build a standalone executable

```
build.bat
```

Produces `dist\Saaaveit\Saaaveit.exe` (PyInstaller onedir, icon from
`ui/branding`).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -q
```

The QML tests run the real `Main.qml` against the real bridge with
`QT_QPA_PLATFORM=offscreen`, so no window appears and no network is used.
The suite never reads or writes your real settings store.

## Layout

```
app/
  bridge.py        the QML bridge: inspection, download, queue, library, settings
  queue.py         one snapshot per queued job, run strictly one at a time
  workers.py       background inspection + download workers
src/
  media_source.py  inspection matrix, subtitle tracks, yt-dlp downloads
  ytdlp.py         locating and running yt-dlp (source and frozen)
  store.py         persisted settings and download history
ui/
  qml/             Theme singleton, components, pages, Main.qml
  branding/        logo marks and the app icon
  fonts/           bundled UI fonts (SIL OFL)
tools/             offscreen screenshots, DPI and keyboard audits
tests/             pytest suite
```

## A note on legality

Saaaveit is a front-end for `yt-dlp`; it adds no access to anything you could
not already reach. Downloading content can violate a platform's terms of
service or copyright law depending on where you are and what you fetch. Use it
only for content you have the right to save.
