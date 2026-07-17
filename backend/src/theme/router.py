from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.auth.service import require_auth
from src.html import hero_image, page

router = APIRouter(tags=["theme"], dependencies=[Depends(require_auth)])

# A representative cover, rendered through the same /cover duotone pipeline
# as every other cover image, so the sliders below have something to
# preview live against instead of only affecting images elsewhere in the
# app. hero_image() wraps this in /cover itself - pass the original Spotify
# URL here, not an already-wrapped one.
_PREVIEW_IMAGE_URL = "https://image-cdn-fa.spotifycdn.com/image/ab67706c0000da842386ebf29b389a9682f494a6"

# (CSS custom property, label) — matches the semantic tokens defined in
# frontend/static/style.css. Defaults aren't duplicated here: the page reads
# each token's current value straight from the stylesheet via
# getComputedStyle, so this list can never drift out of sync on values, only
# on which tokens exist.
TOKENS = [
    ("--color-bg", "Background"),
    ("--color-text", "Text"),
    ("--color-surface", "Surface"),
    ("--color-border", "Border"),
    ("--color-nav-bg", "Nav background"),
    ("--color-accent", "Accent"),
    ("--color-accent-soft", "Accent (soft)"),
    ("--color-selected", "Selected"),
]

# (CSS custom property, label, min, max, unit) — the duotone-mapped cover
# art (/cover) reads flat on its own, so these let saturation/brightness/hue
# be adjusted per browser, same override mechanism as TOKENS but a numeric
# range instead of a color picker.
RANGE_TOKENS = [
    ("--cover-saturate", "Cover saturation", 0, 300, "%"),
    ("--cover-brightness", "Cover brightness", 0, 250, "%"),
    ("--cover-hue", "Cover hue shift", -180, 180, "deg"),
]


@router.get(
    "/theme",
    response_class=HTMLResponse,
    status_code=200,
    description="Locally override color tokens (browser-only, never sent to the server)",
)
def theme_page():
    rows = "".join(
        f"""
<div class="theme-row" data-var="{var}">
  <span class="theme-label">{label}</span>
  <input type="color" class="theme-swatch">
  <input type="text" class="theme-hex" maxlength="7" spellcheck="false">
  <button type="button" class="theme-clear">Clear</button>
</div>"""
        for var, label in TOKENS
    )
    range_rows = "".join(
        f"""
<div class="theme-row theme-range-row" data-var="{var}" data-unit="{unit}">
  <span class="theme-label">{label}</span>
  <input type="range" class="theme-range" min="{lo}" max="{hi}">
  <span class="theme-range-value"></span>
  <button type="button" class="theme-clear">Clear</button>
</div>"""
        for var, label, lo, hi, unit in RANGE_TOKENS
    )
    content = f"""
<h1>Theme</h1>
<p class="subtitle">Override color tokens for this browser only — nothing here is sent to
the server or seen by anyone else. Changes apply immediately and persist across visits on
this device until cleared.</p>
<button type="button" id="theme-reset-all" class="btn">Reset all</button>
<div class="theme-grid">
{rows}
</div>
<h2>Cover art</h2>
{hero_image(_PREVIEW_IMAGE_URL)}
<div class="theme-grid">
{range_rows}
</div>
<script src="/static/theme.js"></script>
"""
    return page(content)
