"""WCAG contrast guard for ``Theme.qml`` (T7.1).

``Theme.qml`` claims that every accent clears AA against ``accentInk`` and that
the text ramp clears 4.5:1 on its worst surface. This test re-derives those
ratios from the token file itself, so a "prettier" hex that dips below the bar
fails the build instead of quietly shipping.

The tokens are parsed from the QML source rather than evaluated in an engine:
the file is the contract, and a parser keeps the test dependency-free and
fast.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

THEME = Path(__file__).resolve().parent.parent / "ui" / "qml" / "Theme.qml"

# readonly property color name: isDark ? "#RRGGBB" : "#RRGGBB"
_COLOR_RE = re.compile(
    r'readonly property color (\w+):\s*isDark\s*\?\s*"([^"]+)"\s*:\s*"([^"]+)"'
)
_ACCENT_RE = re.compile(
    r'\{\s*id:\s*"(\w+)",\s*label:\s*"[^"]+",\s*dark:\s*"([^"]+)",\s*light:\s*"([^"]+)"\s*\}'
)


def _tokens() -> dict[str, tuple[str, str]]:
    """name -> (dark hex, light hex)."""
    text = THEME.read_text(encoding="utf-8")
    return {m.group(1): (m.group(2), m.group(3)) for m in _COLOR_RE.finditer(text)}


def _accents() -> dict[str, tuple[str, str]]:
    text = THEME.read_text(encoding="utf-8")
    return {m.group(1): (m.group(2), m.group(3)) for m in _ACCENT_RE.finditer(text)}


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    assert len(h) == 6, f"not a 6-digit hex colour: {hex_color!r}"
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(hex_color: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = [channel(c) for c in _rgb(hex_color)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colours (1.0–21.0)."""
    l1, l2 = _luminance(fg), _luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _blend(fg_hex: str, alpha: float, bg_hex: str) -> tuple[float, float, float]:
    """``fg`` at ``alpha`` over ``bg``, the way Qt composites: in sRGB space."""
    return tuple(alpha * f + (1.0 - alpha) * b
                 for f, b in zip(_rgb(fg_hex), _rgb(bg_hex)))


def _ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    l1 = 0.2126 * channel(fg[0]) + 0.7152 * channel(fg[1]) + 0.0722 * channel(fg[2])
    l2 = 0.2126 * channel(bg[0]) + 0.7152 * channel(bg[1]) + 0.0722 * channel(bg[2])
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


_TINT_ALPHA = re.compile(
    r'readonly property color (\w*Tint\w*|accentSoft):\s*'
    r'Qt\.rgba\(([\w.]+),\s*[\w.]+,\s*[\w.]+,\s*isDark\s*\?\s*([0-9.]+)\s*:\s*([0-9.]+)\)'
)


def _tints() -> dict[str, tuple[str, float, float]]:
    """tint token -> (colour it tints, dark alpha, light alpha).

    Read from ``Theme.qml`` rather than hard-coded: a tint becoming more
    generous is exactly the change that would quietly break the label on it.
    """
    text = THEME.read_text(encoding="utf-8")
    return {m.group(1): (m.group(2), float(m.group(3)), float(m.group(4)))
            for m in _TINT_ALPHA.finditer(text)}


T = _tokens()


def _pair(name: str) -> tuple[str, str]:
    assert name in T, f"token {name!r} is not a dark/light colour pair in Theme.qml"
    return T[name]


# --- Accents on their own ink -------------------------------------------------
# The claim in Theme.qml: every swatch clears AA against accentInk, in both
# themes. That single ink is what makes one button style legal for five accents.

ACCENT_INK = _pair("accentInk")


@pytest.mark.parametrize("accent", sorted(_accents()))
def test_accent_swatch_clears_aa_on_accent_ink(accent: str) -> None:
    dark_hex, light_hex = _accents()[accent]
    ink_dark, ink_light = ACCENT_INK
    ratio_dark = contrast(dark_hex, ink_dark)
    ratio_light = contrast(light_hex, ink_light)
    assert ratio_dark >= 4.5, (
        f"{accent} (dark) on accentInk: {ratio_dark:.2f}:1 < 4.5:1")
    assert ratio_light >= 4.5, (
        f"{accent} (light) on accentInk: {ratio_light:.2f}:1 < 4.5:1")


# --- Text ramp on its worst surface -------------------------------------------
# "Worst" = the surface with the lowest contrast for that text colour. The ramp
# is only guaranteed as running text, so it must clear AA everywhere it lands.

_TEXT_TOKENS = ("text", "textDim", "textMuted")
_SURFACES = ("background", "surface", "surfaceAlt", "surfaceRaised", "inset")


@pytest.mark.parametrize("token", _TEXT_TOKENS)
def test_text_ramp_clears_aa_on_every_surface(token: str) -> None:
    dark_hex, light_hex = _pair(token)
    for surface in _SURFACES:
        s_dark, s_light = _pair(surface)
        ratio_dark = contrast(dark_hex, s_dark)
        ratio_light = contrast(light_hex, s_light)
        assert ratio_dark >= 4.5, (
            f"{token} on {surface} (dark): {ratio_dark:.2f}:1 < 4.5:1")
        assert ratio_light >= 4.5, (
            f"{token} on {surface} (light): {ratio_light:.2f}:1 < 4.5:1")


# --- Status colours as running text --------------------------------------------
# The status ramp is used for chip labels and row states, not just fills, so it
# must clear AA on the surface chips actually sit on (surfaceRaised).

_STATUS_TOKENS = ("success", "warning", "error", "info")


@pytest.mark.parametrize("token", _STATUS_TOKENS)
def test_status_colour_clears_aa_on_surface_raised(token: str) -> None:
    dark_hex, light_hex = _pair(token)
    s_dark, s_light = _pair("surfaceRaised")
    ratio_dark = contrast(dark_hex, s_dark)
    ratio_light = contrast(light_hex, s_light)
    assert ratio_dark >= 4.5, (
        f"{token} on surfaceRaised (dark): {ratio_dark:.2f}:1 < 4.5:1")
    assert ratio_light >= 4.5, (
        f"{token} on surfaceRaised (light): {ratio_light:.2f}:1 < 4.5:1")


# --- Borders are visible, not decorative ---------------------------------------
# WCAG 1.4.11 asks 3:1 for meaningful non-text contrast, but a hairline divider
# only needs to register; 1.2:1 is the agreed floor here. Anything lower is not
# a border, it is a rumour.

_BORDER_TOKENS = ("border", "borderSoft", "borderStrong")


@pytest.mark.parametrize("token", _BORDER_TOKENS)
def test_borders_register_against_the_surface(token: str) -> None:
    dark_hex, light_hex = _pair(token)
    s_dark, s_light = _pair("surface")
    ratio_dark = contrast(dark_hex, s_dark)
    ratio_light = contrast(light_hex, s_light)
    assert ratio_dark >= 1.2, (
        f"{token} on surface (dark): {ratio_dark:.2f}:1 < 1.2:1")
    assert ratio_light >= 1.2, (
        f"{token} on surface (light): {ratio_light:.2f}:1 < 1.2:1")


# --- The tinted surfaces -------------------------------------------------------
# Every check above compares two opaque hexes. Half the app paints a *translucent*
# fill instead: `accentSoft` marks the selected row of a table, a combo or the
# palette, and `toneTint` is the background of a status chip. The colour that
# actually sits under the label is that blend, and a tint of a colour is always
# nearer that colour than the surface it tints — so every ratio here is worse
# than the opaque one it replaces. (Review F7.)

_TINTED_TOKENS = ("text", "textDim")


def _accents_by_theme() -> tuple[dict[str, str], dict[str, str]]:
    accents = _accents()
    return ({k: v[0] for k, v in accents.items()},
            {k: v[1] for k, v in accents.items()})


def test_accent_soft_is_reachable():
    """Guard for the parser below: the tint tokens must be found at all."""
    tints = _tints()
    assert {"accentSoft", "successTint", "warningTint", "errorTint", "infoTint"} <= set(tints)


@pytest.mark.parametrize("token", _TINTED_TOKENS)
def test_running_text_clears_aa_on_an_accent_tint(token: str) -> None:
    """Selected rows are the app's most common tint — text must survive them."""
    dark_accents, light_accents = _accents_by_theme()
    _, soft_dark, soft_light = _tints()["accentSoft"]
    text_dark, text_light = _pair(token)
    for surface in _SURFACES:
        s_dark, s_light = _pair(surface)
        for name, hex_dark in dark_accents.items():
            bg = _blend(hex_dark, soft_dark, s_dark)
            ratio = _ratio(_rgb(text_dark), bg)
            assert ratio >= 4.5, (
                f"{token} on {name}'s accentSoft over {surface} (dark): {ratio:.2f}:1 < 4.5:1")
        for name, hex_light in light_accents.items():
            bg = _blend(hex_light, soft_light, s_light)
            ratio = _ratio(_rgb(text_light), bg)
            assert ratio >= 4.5, (
                f"{token} on {name}'s accentSoft over {surface} (light): {ratio:.2f}:1 < 4.5:1")


@pytest.mark.parametrize("token", _STATUS_TOKENS)
def test_status_colour_clears_aa_on_its_own_tint(token: str) -> None:
    """``Chip`` paints `toneTint(tone)` behind a label in `tone`.

    The opaque check above is not enough: the chip's own tint is the surface
    the words actually sit on.
    """
    dark_hex, light_hex = _pair(token)
    _, alpha_dark, alpha_light = _tints()[token + "Tint"]
    for surface in _SURFACES:
        s_dark, s_light = _pair(surface)
        ratio_dark = _ratio(_rgb(dark_hex), _blend(dark_hex, alpha_dark, s_dark))
        ratio_light = _ratio(_rgb(light_hex), _blend(light_hex, alpha_light, s_light))
        assert ratio_dark >= 4.5, (
            f"{token} on {token}Tint over {surface} (dark): {ratio_dark:.2f}:1 < 4.5:1")
        assert ratio_light >= 4.5, (
            f"{token} on {token}Tint over {surface} (light): {ratio_light:.2f}:1 < 4.5:1")


def test_accent_on_its_own_tint_is_a_shape_not_a_word():
    """Why the two tests above exist.

    Raw accent over its own tint clears the 3:1 that WCAG 1.4.11 asks of a
    graphic — a selection dot, a chevron, a rail icon — but never the 4.5 a
    word needs. So `Theme.accent` is legal as a fill and illegal as `color:`
    on a tinted row, and this floor is what keeps the fill honest.
    """
    dark_accents, light_accents = _accents_by_theme()
    _, soft_dark, soft_light = _tints()["accentSoft"]
    for name, hex_dark in dark_accents.items():
        for surface in _SURFACES:
            s_dark = _pair(surface)[0]
            ratio = _ratio(_rgb(hex_dark), _blend(hex_dark, soft_dark, s_dark))
            assert ratio >= 3.0, (
                f"{name} on its own accentSoft over {surface} (dark): {ratio:.2f}:1 < 3:1")
    for name, hex_light in light_accents.items():
        for surface in _SURFACES:
            s_light = _pair(surface)[1]
            ratio = _ratio(_rgb(hex_light), _blend(hex_light, soft_light, s_light))
            assert ratio >= 3.0, (
                f"{name} on its own accentSoft over {surface} (light): {ratio:.2f}:1 < 3:1")


# --- accentOnTint: the one derived colour the UI uses as text ------------------
# `Chip` cannot paint a label in raw accent on its own tint (3.57:1, above), so
# Theme derives a pushed-along-the-same-hue variant with Qt.lighter/darker. QColor
# reproduces that arithmetic without an engine, which keeps this the same
# parse-the-token-file test as everything else.

_ACCENT_ON_TINT = re.compile(
    r'accentOnTint:\s*isDark\s*\?\s*Qt\.lighter\(accent,\s*([0-9.]+)\)\s*'
    r':\s*Qt\.darker\(accent,\s*([0-9.]+)\)'
)


def _to_tuple(color) -> tuple[float, float, float]:
    return (color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0)


def _blend_qcolor(fg_hex: str, alpha: float, bg_hex: str):
    from PySide6.QtGui import QColor

    f, b = QColor(fg_hex), QColor(bg_hex)
    return QColor(round(alpha * f.red() + (1 - alpha) * b.red()),
                  round(alpha * f.green() + (1 - alpha) * b.green()),
                  round(alpha * f.blue() + (1 - alpha) * b.blue()))


def test_accent_on_tint_clears_aa_on_every_surface() -> None:
    text = THEME.read_text(encoding="utf-8")
    match = _ACCENT_ON_TINT.search(text)
    assert match, (
        "accentOnTint must stay `isDark ? Qt.lighter(accent, k) : "
        "Qt.darker(accent, k)` for this test to be able to evaluate it")
    lighter, darker = float(match.group(1)), float(match.group(2))
    from PySide6.QtGui import QColor

    _, soft_dark, soft_light = _tints()["accentSoft"]
    for name, (hex_dark, hex_light) in _accents().items():
        for surface in _SURFACES:
            s_dark, s_light = _pair(surface)
            fg_dark = QColor(hex_dark).lighter(int(round(lighter * 100)))
            fg_light = QColor(hex_light).darker(int(round(darker * 100)))
            ratio_dark = _ratio(_to_tuple(fg_dark),
                                _to_tuple(_blend_qcolor(fg_dark.name(), soft_dark, s_dark)))
            ratio_light = _ratio(_to_tuple(fg_light),
                                 _to_tuple(_blend_qcolor(fg_light.name(), soft_light, s_light)))
            assert ratio_dark >= 4.5, (
                f"{name} as accentOnTint over {surface} (dark): {ratio_dark:.2f}:1 < 4.5:1")
            assert ratio_light >= 4.5, (
                f"{name} as accentOnTint over {surface} (light): {ratio_light:.2f}:1 < 4.5:1")
