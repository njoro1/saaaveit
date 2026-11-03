pragma Singleton
import QtQuick

// Design tokens for the "UI redesign" reference.
//
// Every visual value lives here so the whole UI can change appearance from one
// place, and so the QML maps 1:1 onto ``Saaaveit — UI redesign.html``.
// Where a reference colour fails the WCAG floors that
// ``tests/test_theme_contrast.py`` enforces, the nearest passing value is
// adopted instead — each nudge is recorded at the token.
//
// Two axes are pushed in from Main.qml (a singleton cannot reliably read the
// ``appBridge`` context property):
//   * themeName   - "dark" (default) | "light"
//   * comfortable - larger hit targets and +1px text
//   * reducedMotion - pulsing dots and sliding bars stop
//   * accentName  - one of ``accentChoices``; picks the brand hue
QtObject {
    // --- Appearance mode -------------------------------------------------
    property string themeName: "dark"
    readonly property bool isDark: themeName !== "light"

    property bool comfortable: false
    readonly property int fontBoost: comfortable ? 1 : 0

    property bool reducedMotion: false

    // --- Accent presets ---------------------------------------------------
    // The Settings page shows these as swatches. ``accentName`` is persisted by
    // the bridge; everything else derives from it.
    // Every swatch clears WCAG AA (4.5:1) against `accentInk`, in its own theme
    // — that is what makes one ink token legal for all six. `tests/
    // test_theme_contrast.py` re-derives the ratios from this table, so a
    // "prettier" hex that dips below the bar fails the build.
    //
    // `cobalt` is the brand hue: its light value is the logo tile's own
    // `#2F6FEB` from `ui/branding`, unchanged. White ink on it measures 4.57:1,
    // which clears AA by 0.07 — the tightest margin in the table, and the one
    // that must not be nudged darker for taste. The dark value is the same hue
    // lifted to `#5A95F5` (6.44:1 against `#0D0E1A`), because `#2F6FEB` is too
    // dark for the near-black page and would fail the 3:1 shape floor as a rail
    // icon. The logo tile itself is exempt: it is brand ink and never follows
    // this token.
    readonly property var accentChoices: [
        { id: "cobalt", label: "Cobalt", dark: "#5A95F5", light: "#2F6FEB" },
        { id: "iris",   label: "Iris",   dark: "#8b8fff", light: "#4a4fd8" },
        { id: "azure",  label: "Azure",  dark: "#5ab0f0", light: "#1a6fb0" },
        { id: "mint",   label: "Mint",   dark: "#4cc38a", light: "#17824f" },
        { id: "amber",  label: "Amber",  dark: "#e5b04a", light: "#946500" },
        { id: "rose",   label: "Rose",   dark: "#f28aa8", light: "#c23b6a" }
    ]
    property string accentName: "cobalt"

    function _accentFor(name, dark) {
        for (let i = 0; i < accentChoices.length; i++) {
            if (accentChoices[i].id === name)
                return dark ? accentChoices[i].dark : accentChoices[i].light
        }
        return dark ? "#5a95f5" : "#2f6feb"
    }

    // --- Spacing scale (4px base) ----------------------------------------
    // Density reaches the spacing scale as well as the type scale. Without
    // this, "Comfortable" only grew the text and the controls, so a
    // comfortable window was *tighter* than a compact one — more pixels of
    // glyph in the same gaps. `xs` stays at 4px: it is used for hairline
    // gaps inside a single control, which must not move.
    readonly property int xs: 4
    readonly property int sm: comfortable ? 10 : 8
    readonly property int md: comfortable ? 14 : 12
    readonly property int lg: comfortable ? 20 : 16
    readonly property int xl: comfortable ? 28 : 24
    readonly property int xxl: comfortable ? 38 : 32

    // --- Radii ------------------------------------------------------------
    readonly property int radiusXs: 6
    readonly property int radiusSm: 8
    readonly property int radiusMd: 10
    readonly property int radiusLg: 12
    readonly property int radiusXl: 16

    // --- Type scale (12 / 13 / 14 / 15 / 17 / 21 / 26) ---------------------
    // Desktop baselines: nothing below 12px, body at 14px. The previous ramp
    // (13px body, 10px table headers) read as a dense admin tool.
    readonly property int fontTiny: 12 + fontBoost
    readonly property int fontSmall: 13 + fontBoost
    readonly property int fontBody: 14 + fontBoost
    readonly property int fontLabel: 15 + fontBoost
    readonly property int fontTitle: 17 + fontBoost
    readonly property int fontH2: 21 + fontBoost
    readonly property int fontH1: 26 + fontBoost
    // ``h1{letter-spacing:-.01em}`` — the only tracked text in the reference.
    // Expressed as a fraction of the size so it survives the density step.
    readonly property real h1Tracking: -0.01 * fontH1

    // --- Surfaces ---------------------------------------------------------
    // The reference's four-step ramp: page (`background`), card (`surface`),
    // banded row / secondary card (`surfaceAlt`), raised or hovered row
    // (`surfaceRaised`), recessed input (`inset`).
    readonly property color background: isDark ? "#121418" : "#F3F4F7"
    readonly property color backgroundGlow: isDark
        ? Qt.rgba(0.541, 0.420, 1.0, 0.07) : Qt.rgba(0.357, 0.239, 0.961, 0.06)
    readonly property color surface: isDark ? "#191C22" : "#FFFFFF"
    readonly property color surfaceAlt: isDark ? "#20242B" : "#F0F1F5"
    readonly property color surfaceRaised: isDark ? "#282D36" : "#E5E7EE"
    readonly property color inset: isDark ? "#0E1013" : "#E9EBF1"
    // The old name for the app-chrome band, kept so nothing that still refers
    // to it breaks.
    readonly property color headerBackground: isDark ? "#191C22" : "#FFFFFF"
    // Reference `b1` is #262b33, which measures 1.199:1 on `surface` — one
    // thousandth under the 1.2 floor this repo enforces. Lifted to #272c35.
    readonly property color border: isDark ? "#272C35" : "#E1E4EA"
    // `borderSoft` is the hairline under a card header. It has to survive the
    // WCAG 1.4.11 non-text bar (>= 1.2:1 against `surface`) or it is not a
    // border, it is a rumour. In dark it is indistinguishable from `border`
    // (the reference's two steps collapse at this luminance).
    readonly property color borderSoft: isDark ? "#272C35" : "#E3E6EC"
    readonly property color borderStrong: isDark ? "#343A45" : "#C9CED8"

    // --- Elevation --------------------------------------------------------
    // Depth is a system value, not a per-component decision: cards may carry
    // exactly one level-1 shadow, and only overlays (palette, dialogs, menus)
    // may use level 3. Nothing else casts a shadow — a blur behind scrolling
    // content costs a repaint per frame.
    readonly property int elevationNone: 0
    readonly property int elevationCard: 1
    readonly property int elevationOverlay: 3

    // Dark surfaces sit on a near-black page, so their shadows need more
    // opacity to register; light surfaces need much less or the shadow reads
    // as a second border.
    readonly property color shadowColor: isDark ? "#000000" : "#0F172A"
    readonly property real shadowOpacityCard: isDark ? 0.45 : 0.10
    readonly property int shadowBlurCard: 14
    readonly property int shadowYOffsetCard: 4
    readonly property real shadowOpacityOverlay: isDark ? 0.55 : 0.18
    readonly property int shadowBlurOverlay: 28
    readonly property int shadowYOffsetOverlay: 10

    function shadowFor(level) {
        if (level >= elevationOverlay)
            return { opacity: shadowOpacityOverlay, blur: shadowBlurOverlay,
                     yOffset: shadowYOffsetOverlay }
        if (level >= elevationCard)
            return { opacity: shadowOpacityCard, blur: shadowBlurCard,
                     yOffset: shadowYOffsetCard }
        return { opacity: 0, blur: 0, yOffset: 0 }
    }

    // Scrim behind overlays (palette, dialogs). The reference dims toward
    // black at the same alpha in both themes.
    readonly property color scrim: Qt.rgba(0, 0, 0, isDark ? 0.50 : 0.50)

    // --- Text -------------------------------------------------------------
    // Three steps of the same ramp. All three are read as running text, so all
    // three clear AA (4.5:1) on the *lightest* surface they can land on —
    // `surfaceRaised` in dark, `background` in light — and on every accent
    // tint. `text` is the reference's `tx`; the two helper steps are nudged
    // from its `mu` (#9aa1ad measures 4.01:1 on a tint), staying the same hue.
    readonly property color text: isDark ? "#E8EAEE" : "#1A1D24"
    readonly property color textDim: isDark ? "#B9C0CA" : "#4C5261"
    readonly property color textMuted: isDark ? "#AAB1BD" : "#565D6D"

    // --- Brand / semantics ------------------------------------------------
    readonly property color accent: _accentFor(accentName, isDark)
    readonly property color accentHover: Qt.lighter(accent, isDark ? 1.18 : 1.12)
    // The label painted *on top of* a filled accent surface — the primary
    // action, the active segment, the error badge. Dark-theme accents are
    // bright pastels (so they read as text on a near-black page), which means
    // white ink lands at 2.0–4.3:1 on them; a near-black ink clears AA on every
    // swatch and on `error` too. Hence the flip rather than a fixed white.
    // Reference ink: `#0d0e1a` on the dark fills, white on the light ones.
    readonly property color accentInk: isDark ? "#0D0E1A" : "#FFFFFF"
    // Legacy alias used by older call sites.
    readonly property color accentText: accentInk
    readonly property color accentSoft: Qt.rgba(accent.r, accent.g, accent.b, isDark ? 0.14 : 0.10)
    // The reference draws selection borders as `c+'99'` — 60% of the hue, at or
    // near opaque — so this is far stronger than the old 0.35–0.38.
    readonly property color accentLine: Qt.rgba(accent.r, accent.g, accent.b, isDark ? 0.55 : 0.60)
    // The accent as *text on a tinted surface* — an "available in this codec"
    // chip. Raw accent on accentSoft is 3.57:1 at worst, which is a shape's
    // number; pushing the same hue away from the surface it sits on keeps the
    // identity and clears AA. Never use `accent` for a label on a tint.
    readonly property color accentOnTint: isDark ? Qt.lighter(accent, 1.35)
                                                 : Qt.darker(accent, 1.55)

    // Status colours are running text (a chip label, an error row), so they are
    // set by their worst *real* background rather than a plain surface: `Chip`
    // paints `toneTint(tone)` — 10–13% of the hue over the surface beneath it —
    // and the darkest light surface is `surfaceRaised`. The reference's light
    // steps (#17824f, #8f6200, #c23b3b, #1a6fb0) land at 3.7–4.4:1 there, and
    // its dark `error` (#f26d6d) at 3.96 on its own tint, so the four are the
    // nearest passing values; dark success/warning/info are the reference's.
    //
    // They no longer match the `mint` / `amber` / `rose` accent swatches exactly:
    // those are fills read through `accentInk`, where a deeper value would only
    // muddy the page.
    readonly property color success: isDark ? "#4CC38A" : "#12683F"
    readonly property color warning: isDark ? "#E5B04A" : "#7B5400"
    readonly property color error: isDark ? "#FF858A" : "#A33232"
    readonly property color info: isDark ? "#5AB0F0" : "#165F97"

    readonly property color errorHover: Qt.lighter(error, 1.12)
    readonly property color warningHover: Qt.lighter(warning, 1.12)

    readonly property color successTint: Qt.rgba(success.r, success.g, success.b, isDark ? 0.13 : 0.11)
    readonly property color warningTint: Qt.rgba(warning.r, warning.g, warning.b, isDark ? 0.13 : 0.11)
    readonly property color errorTint: Qt.rgba(error.r, error.g, error.b, isDark ? 0.13 : 0.10)
    readonly property color infoTint: Qt.rgba(info.r, info.g, info.b, isDark ? 0.13 : 0.10)
    readonly property color accentTint: accentSoft

    // The mark painted *inside* a solid status fill — the step-completed ✓ on a
    // green dot, the glyph on an error badge. The reference uses a near-black
    // that reads better on a pastel fill than white does; light theme fills are
    // deep, so they take white.
    readonly property color statusOnFill: isDark ? "#06150E" : "#FFFFFF"

    // Secret fields (API key) get a recessed background in both themes.
    readonly property color fieldSecretBackground: isDark ? "#0E1013" : "#E9EBF1"

    // --- Fonts ------------------------------------------------------------
    // Qt takes one family name, never a comma list, so resolve the first
    // *installed* candidate. Asking for a family that is not there makes Qt
    // substitute silently (different metrics per machine) and logs a missing
    // family warning. ``_fontFamilies`` is captured once, not per lookup.
    readonly property var _fontFamilies: Qt.fontFamilies()
    readonly property string _systemFont: Qt.application.font ? Qt.application.font.family : ""

    function pickFamily(candidates) {
        var installed = _fontFamilies || []
        for (var i = 0; i < candidates.length; i++) {
            var want = (candidates[i] || "").toLowerCase()
            if (!want)
                continue
            for (var j = 0; j < installed.length; j++) {
                if (installed[j].toLowerCase() === want)
                    return installed[j]
            }
        }
        // Nothing matched: still return a real-ish name rather than "".
        return candidates[candidates.length - 1]
    }

    readonly property string uiFont: pickFamily([
        // Bundled with the app (``ui/fonts``, SIL OFL) and registered in
        // main.py, so the reference's own face is the one that always wins.
        "Hanken Grotesk",
        _systemFont,
        "Segoe UI Variable Text", "Segoe UI", "Inter",
        "Noto Sans", "DejaVu Sans", "Arial"
    ])
    // Monospace is chosen from a list for the same reason; numeric columns
    // (size, percent, paths) must stay aligned.
    readonly property string monoFont: pickFamily([
        "IBM Plex Mono",
        "Cascadia Mono", "Cascadia Code", "Consolas",
        "DejaVu Sans Mono", "Courier New"
    ])

    // --- Geometry ---------------------------------------------------------
    // Named after the reference's own classes (``.ri``, ``.in``, ``.cell``,
    // ``.panel``, ``.drw``, ``.dot``) so a value here can be checked against the
    // prototype line by line.
    readonly property int controlHeight: comfortable ? 38 : 34
    readonly property int controlHeightSmall: comfortable ? 32 : 28
    readonly property int rowHeight: comfortable ? 40 : 34
    // Legacy alias: ``fieldHeight`` was the old control height.
    readonly property int fieldHeight: controlHeight
    readonly property int topbarHeight: 48
    // ``.top{padding:0 20px}`` — wider than the status bar's 16px, and not a
    // density value: the reference never changes it.
    readonly property int topbarPaddingH: 20
    readonly property int railWidth: 64
    readonly property int railItemSize: 42
    readonly property int statusbarHeight: 30
    // Content stops growing past this width so long rows stay readable.
    readonly property int contentMaxWidth: 1180
    readonly property int pagePaddingH: 32
    readonly property int pagePaddingV: 28
    // Text fields sit taller than buttons (``.in`` 44 vs ``.btn`` 34); selects
    // keep the reference's 38.
    readonly property int inputHeight: comfortable ? 48 : 44
    readonly property int selectHeight: comfortable ? 42 : 38
    // A field inside a settings row is one step shorter than the page's URL
    // field (`#tpl`/`#rst` carry `height:36px`), so the row stays 14px of air
    // rather than growing around a 44px control.
    readonly property int rowInputHeight: comfortable ? 38 : 36
    readonly property int primaryActionHeight: comfortable ? 44 : 40
    // ``.btn`` sits one step tighter than an input's 10px corner.
    readonly property int buttonRadius: 9
    // The format matrix: a 72px label column, three equal codec columns, 6px
    // gutters, 50px cells (56 comfortable).
    readonly property int matrixLabelWidth: 72
    readonly property int matrixGap: 6
    readonly property int matrixCellHeight: comfortable ? 56 : 50
    // Sticky sibling panels: download summary, library drawer.
    readonly property int panelWidth: 340
    readonly property int drawerWidth: 320
    // ``.dl{gap:28px}`` — the flow column and its sticky summary.
    readonly property int columnGap: 28
    // ``.libwrap{gap:18px}`` — the list and its drawer sit a step tighter than
    // the download flow, so the drawer reads as part of the list.
    readonly property int drawerGap: 18
    // ``.lib`` grid columns: 64 thumb / flex name / 80 size / 130 when /
    // 150 actions. When a row is selected the page collapses the last two.
    readonly property int listThumbWidth: 64
    readonly property int listSizeWidth: 80
    readonly property int listWhenWidth: 130
    readonly property int listActionWidth: 150
    // Step rail: a 28px numeral dot, a 40px gutter, a 2px connector.
    readonly property int stepDotSize: 28
    readonly property int stepGutter: 40
    readonly property int stepLineWidth: 2
    // ``.step`` bottom padding - the gap between one step's body and the next
    // step's dot.
    readonly property int stepGap: 26
    readonly property int heroThumbWidth: comfortable ? 198 : 176
    readonly property int heroTitleSize: 16 + fontBoost
    readonly property int statusMarkSize: 18
    // ``radiusLg`` stays for chrome that is not a card; the reference's cards and
    // drawers are 14, its dialogs 16, its chips a pill.
    readonly property int cardRadius: 14
    readonly property int dialogRadius: 16
    readonly property int radiusCircle: 999
    // Legacy alias.
    readonly property int headerHeight: topbarHeight

    // --- Status helpers ---------------------------------------------------
    // Row state must never rely on colour alone (WCAG 1.4.1), so every status
    // carries an icon and a word as well as a colour.
    function statusIcon(status) {
        if (status === "untranslated" || status === "empty") return "!"
        if (status === "warning") return "\u25B2"
        return "\u2713"
    }

    function statusLabel(status) {
        if (status === "untranslated") return "Untranslated"
        if (status === "empty") return "Empty"
        if (status === "warning") return "Warning"
        return "OK"
    }

    function statusColor(status) {
        if (status === "untranslated" || status === "empty") return error
        if (status === "warning") return warning
        return success
    }

    function statusTint(status) {
        if (status === "untranslated" || status === "empty") return errorTint
        if (status === "warning") return warningTint
        return successTint
    }

    // --- Ring treatment for the two "no verdict" states -------------------
    // `unchecked` is an open ring (we have not looked yet). `na` is a closed
    // muted ring with a dash (this mode never uses it). They are different
    // facts and must not collapse into one grey dash — that collapse is what
    // made the readiness denominator disagree with the visible rows, so the
    // pair lives here rather than being re-invented per page.
    function statusRing(status) {
        if (status === "unchecked") return borderStrong
        if (status === "na") return border
        return "transparent"
    }

    function statusRingWidth(status) {
        if (status === "unchecked") return 1.5
        if (status === "na") return 1
        return 0
    }

    // Tone name -> colour / tint. Used by pills, chips, tiles and badges so the
    // palette lives in exactly one place.
    function toneColor(tone) {
        if (tone === "ok") return success
        if (tone === "warn") return warning
        if (tone === "err") return error
        if (tone === "info") return info
        if (tone === "acc") return accent
        return textMuted
    }

    function toneTint(tone) {
        if (tone === "ok") return successTint
        if (tone === "warn") return warningTint
        if (tone === "err") return errorTint
        if (tone === "info") return infoTint
        if (tone === "acc") return accentSoft
        return surfaceRaised
    }

    function toneBorder(tone) {
        if (tone === "ok") return Qt.rgba(success.r, success.g, success.b, 0.30)
        if (tone === "warn") return Qt.rgba(warning.r, warning.g, warning.b, 0.30)
        if (tone === "err") return Qt.rgba(error.r, error.g, error.b, 0.30)
        if (tone === "info") return Qt.rgba(info.r, info.g, info.b, 0.30)
        if (tone === "acc") return accentLine
        return border
    }

    // --- Small formatters -------------------------------------------------
    function formatDuration(sec) {
        var s = Math.max(0, Math.floor(sec))
        var m = Math.floor(s / 60)
        var rs = s % 60
        return (m > 0 ? m + "m " : "") + rs + "s"
    }

    function formatClock(sec) {
        var s = Math.max(0, Math.floor(sec))
        var m = Math.floor(s / 60)
        var rs = s % 60
        return m + ":" + (rs < 10 ? "0" : "") + rs
    }
}
