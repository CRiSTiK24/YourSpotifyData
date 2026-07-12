import os
import re
from enum import StrEnum


class Palette(StrEnum):
    VERY_DARK_PURPLE = "#2d162c"
    DARK_PURPLE = "#412752"
    PURPLE = "#683a68"
    LIGHT_PURPLE = "#9775a6"
    # neutrals: LIGHT_PURPLE only reaches ~3.2:1 against TEXT, below the 4.5:1
    # AA minimum — it's still used as a fill (buttons, borders) but text on
    # top of it directly (e.g. resting-state button label) is a known
    # legibility tradeoff. TEXT is otherwise the only color used for text.
    TEXT = "#f5eac2"
    BACKGROUND = "#2c1f33"


CSS_VAR_NAMES = {
    Palette.VERY_DARK_PURPLE: "--very-dark-purple",
    Palette.DARK_PURPLE: "--dark-purple",
    Palette.PURPLE: "--purple",
    Palette.LIGHT_PURPLE: "--light-purple",
    Palette.TEXT: "--text",
    Palette.BACKGROUND: "--bg",
}


def css_root_block() -> str:
    lines = "\n".join(f"    {name}: {color.value};" for color, name in CSS_VAR_NAMES.items())
    return f":root {{\n{lines}\n}}"


_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)
_MARKER_RE = re.compile(
    r"/\* palette:start.*?\*/.*?/\* palette:end \*/", re.DOTALL
)


def sync_css_palette() -> None:
    """Rewrite the generated :root block in style.css from this module, so the
    CSS palette can never drift out of sync with Palette."""
    path = os.path.join(_STATIC_DIR, "style.css")
    with open(path) as f:
        css = f.read()
    block = (
        "/* palette:start — generated from src/palette.py, do not edit by hand */\n"
        f"{css_root_block()}\n"
        "/* palette:end */"
    )
    new_css = _MARKER_RE.sub(block, css, count=1)
    if new_css != css:
        with open(path, "w") as f:
            f.write(new_css)
