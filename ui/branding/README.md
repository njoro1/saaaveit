# Saaaveit brand assets — pack C-cobalt

Vendored from `saaaveit-logo-C-cobalt/` at the project root, which keeps the
full delivery (13 PNG sizes, 6 SVGs, the `.ico`, and the one-colour cuts).
Only the four files the app actually loads live here, so the PyInstaller
bundle carries nothing unused.

| File | What it is | Where it is used |
| --- | --- | --- |
| `saaaveit-mark.svg` | 96x96 tile, `#2F6FEB` fill, white glyph | `Brand.qml` variant `mark` — the rail head and the empty screens |
| `saaaveit-lockup-light.svg` | tile + wordmark, `#14161C` ink | `Brand.qml` variant `lockup`, light theme |
| `saaaveit-lockup-dark.svg` | tile + wordmark, white ink | `Brand.qml` variant `lockup`, dark theme |
| `saaaveit-favicon.ico` | 16/32/48/64/128/256 | `main.py` window icon, `Saaaveit.spec` / `build.bat` EXE icon |

## Rules the pack imposes

- **The tile never changes colour.** It is brand ink, so it does not follow
  `Theme.accent`. The accent swatches recolour the UI chrome only.
- **`lockup-light` on light backgrounds, `lockup-dark` on dark.** They differ
  only in wordmark ink; the tile and glyph are identical in both.
- The wordmark is **outlined geometry**, not text — it needs no font at
  runtime. The face it was drawn from is Hanken Grotesk Bold, which is already
  vendored under `ui/fonts/` as SIL OFL 1.1 (see `ui/fonts/README.md`).

Re-export from the pack root if the logo changes, then re-run
`tools/screenshot.py` — the mark appears in the rail, the empty Library screen
and the Environment card.
