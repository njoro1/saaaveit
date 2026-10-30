# Saaaveit

A small desktop app that downloads a video **and**, in the same action,
one of the subtitle tracks the video offers.

This is a standalone codebase. It shares no code, no configuration and no
process with any other application.

## What it does

1. Paste a video URL and press **Inspect**. The app reads the formats the service
   actually serves — AV1, VP9 and H.264 at every available resolution — plus
   every subtitle track (manual and auto-generated, in every language).
2. Pick a codec and resolution. The table and the dropdowns always agree.
3. Pick a subtitle track, or **None — video only**. The default is the video's
   own original language, manual preferred over auto-generated.
4. Press **Download**. The video is fetched first, then the subtitle. If the
   video leg fails, the subtitle leg still runs — the outcome of each leg is
   reported separately.

**Fetch subtitle only** is there for the case where you already have the video.

## Requirements

* Python 3.10+
* `pip install -r requirements.txt`
* `ffmpeg` — `imageio-ffmpeg` provides one; alternatively put `ffmpeg.exe` on
  `PATH`. Without it, separate video and audio streams cannot be merged.

## Run

```
python main.py
```

A URL may be passed on the command line and will be inspected on startup:

```
python main.py https://www.video source.com/watch?v=dQw4w9WgXcQ
```

## Command line

The CLI uses the same engine as the GUI:

```
python cli.py --list-formats URL
python cli.py URL --codec vp9 --resolution 1080 --subs ja
python cli.py URL --subs-only --subs ja -o C:\Downloads
```

## Build a standalone executable

```
build.bat
```

Produces `dist\Saaaveit\Saaaveit.exe` (onedir).

## Layout

```
app/
  bridge.py      the QML bridge: inspection, download, library, settings
  workers.py     background inspection + download workers
src/
  media_id.py  URL -> video id
  media_source.py
                 inspection matrix, subtitle tracks, yt-dlp downloads
  ytdlp.py       locating and running yt-dlp (source and frozen)
  store.py       persisted settings and download history
ui/qml/          Theme, components, pages, Main.qml
tests/           pytest suite
```

## Tests

```
python -m pytest -q
```
