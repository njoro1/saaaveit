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
