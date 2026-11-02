# Bundled fonts

Both families are licensed under the SIL Open Font License 1.1 (full text in
`HankenGrotesk-OFL.txt` and `IBMPlexMono-OFL.txt`, copied alongside).

- **Hanken Grotesk** — Regular/Medium/SemiBold/Bold (400/500/600/700).
  Source: `google/fonts`, `ofl/hankengrotesk/`. The upstream family is shipped
  only as a variable font (`HankenGrotesk[wght].ttf`), which Qt's static font
  database cannot instance, so the four named weights here were produced from
  that VF with `fonttools varLib.instancer` and given proper static name
  tables (family/style/postscript names per weight).
- **IBM Plex Mono** — Regular/Medium (400/500).
  Source: `google/fonts`, `ofl/ibmplexmono/`, unmodified upstream static TTFs.

`main.py` registers every `.ttf` in this folder via
`QFontDatabase.addApplicationFont` before the QML engine loads; `Theme.qml`
lists "Hanken Grotesk" and "IBM Plex Mono" first in its font candidates and
falls back to system fonts if registration ever fails.

The PyInstaller bundle picks this folder up through the existing `('ui', 'ui')`
datas entry in `Saaaveit.spec` (the whole `ui` tree ships recursively).
