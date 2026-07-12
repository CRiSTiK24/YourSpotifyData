from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.auth.service import require_auth
from src.html import page

router = APIRouter(tags=["theme"], dependencies=[Depends(require_auth)])

# (CSS custom property, label) — matches the semantic tokens defined in
# frontend/static/style.css. Defaults aren't duplicated here: the page reads
# each token's current value straight from the stylesheet via
# getComputedStyle, so this list can never drift out of sync on values, only
# on which tokens exist.
TOKENS = [
    ("--color-bg", "Background"),
    ("--color-text", "Text"),
    ("--color-surface", "Surface"),
    ("--color-surface-hover", "Surface hover"),
    ("--color-border", "Border"),
    ("--color-nav-bg", "Nav background"),
    ("--color-accent", "Accent"),
    ("--color-accent-soft", "Accent (soft)"),
    ("--color-selected", "Selected"),
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
    content = f"""
<h1>Theme</h1>
<p class="subtitle">Override color tokens for this browser only — nothing here is sent to
the server or seen by anyone else. Changes apply immediately and persist across visits on
this device until cleared.</p>
<button type="button" id="theme-reset-all" class="btn">Reset all</button>
<div class="theme-grid">
{rows}
</div>
<script src="/static/theme.js"></script>
"""
    return page(content)
