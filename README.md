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
5. Queue as many as you like. While a job runs the form stays usable, the
   primary button reads **Add to queue**, and each job keeps the picks it was
   committed with. Downloads run strictly one at a time, in order; a failed job
   reports its reason on its own row and the batch carries on. The queue is
   saved and comes back stopped, so nothing starts by itself after a restart.

**Fetch subtitle only** is there for the case where you already have the video.

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
  bridge.py      the QML bridge: inspection, download, queue, library, settings
  queue.py       one snapshot per queued job, run strictly one at a time
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
pip install -r requirements-dev.txt
python -m pytest -q
```

The QML tests run the real `Main.qml` against the real bridge with
`QT_QPA_PLATFORM=offscreen`, so no window appears and no network is used.
