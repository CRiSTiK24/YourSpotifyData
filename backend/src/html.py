import os
from contextvars import ContextVar
from html import escape

from fastapi.responses import HTMLResponse

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)

# Set by auth middleware for the duration of each request, so `page()` can
# render the right nav links without every route having to pass auth state
# through explicitly.
logged_in_var: ContextVar[bool] = ContextVar("logged_in", default=False)


def page(content: str) -> HTMLResponse:
    if logged_in_var.get():
        nav_right = """
    <div class="nav-right">
      <a href="/upload">Upload</a>
      <a href="/scrobbler">Scrobbler</a>
      <a href="/theme">Theme</a>
    </div>"""
    else:
        nav_right = """
    <div class="nav-right">
      <a href="/login">Login</a>
    </div>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title></title>
  <link rel="stylesheet" href="/static/style.css">
  <script>
  (function () {{
    try {{
      var overrides = JSON.parse(localStorage.getItem("theme-overrides") || "{{}}");
      for (var key in overrides) document.documentElement.style.setProperty(key, overrides[key]);
    }} catch (e) {{}}
  }})();
  </script>
  <script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
</head>
<body hx-boost="true">
<nav>
  <div class="inner">
    <a class="brand" href="/">Home</a>
    <a href="/liked-songs">Liked Songs</a>
    <a href="/liked-albums">Liked Albums</a>
    <a href="/playlists">Playlists</a>
    <a href="/artists">Artists</a>{nav_right}
  </div>
</nav>
<div class="container">
{content}
</div>
</body>
</html>"""
    return HTMLResponse(html)


def link(label: str, href: str) -> str:
    return f"<a href='{escape(href)}'>{escape(label)}</a>"


def button(label: str, href: str, *, hx_boost: bool | None = None) -> str:
    boost_attr = f" hx-boost='{'true' if hx_boost else 'false'}'" if hx_boost is not None else ""
    return f"<a class='btn' href='{escape(href)}'{boost_attr}>{escape(label)}</a>"


def chip_link(label: str, href: str) -> str:
    return f"<a class='chip-link' href='{escape(href)}'>{escape(label)}</a>"


def back_link(href: str, label: str = "← Back") -> str:
    return f"<a class='back-link' href='{escape(href)}'>{escape(label)}</a>"


def stat_card(title: str, count_label: str) -> str:
    return f"""
  <div class="card">
    <h2>{escape(title)}</h2>
    <p class="count">{escape(count_label)}</p>
  </div>"""


def search_form(
    action: str, placeholder: str, *, value: str = "", autofocus: bool = True, name: str = "query"
) -> str:
    autofocus_attr = " autofocus" if autofocus else ""
    value_attr = f" value='{escape(value)}'" if value else ""
    return f"""
<form class="search-form" action="{escape(action)}" method="get">
  <input name="{escape(name)}" type="text"{value_attr} placeholder="{escape(placeholder)}"{autofocus_attr}>
  <button type="submit">Search</button>
</form>"""


def row(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
) -> str:
    thumb = f"<img class='row-thumb' src='{escape(image_url)}' loading='lazy'>" if image_url else ""
    left = f"<a href='{escape(primary_href)}'>{escape(primary_label)}</a>"
    if secondary_label and secondary_href:
        left += (
            f" <span class='sep'>—</span> "
            f"<a href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        )
    right = f"<span class='note'>{escape(note)}</span>" if note else ""
    return f"<div class='row'><div class='left'>{thumb}{left}</div>{right}</div>"


def hero_image(image_url: str | None) -> str:
    if not image_url:
        return ""
    return f"<img class='hero-image' src='{escape(image_url)}' loading='lazy'>"


def detail_layout(header: str, heatmap: str, list_title: str, list_content: str) -> str:
    """Two-panel layout used by track/album/artist/playlist detail pages:
    header info on the left, heatmap on the right, full-width list below."""
    return f"""
<div class="detail-layout">
  <div class="panel detail-header">{header}</div>
  <div class="panel detail-heatmap">{heatmap}</div>
  <div class="panel detail-list">
    <h2>{escape(list_title)}</h2>
    {list_content}
  </div>
</div>"""


def pagination_html(current_page: int, total_pages: int, base_href: str, param: str) -> str:
    if total_pages <= 1:
        return ""
    half = 4
    p_start = max(1, current_page - half)
    p_end = min(total_pages, p_start + 8)
    p_start = max(1, p_end - 8)
    sep = "&" if "?" in base_href else "?"
    links = []
    if current_page > 1:
        links.append(f"<a href='{base_href}{sep}{param}={current_page - 1}'>‹</a>")
    for p in range(p_start, p_end + 1):
        if p == current_page:
            links.append(f"<span class='current'>{p}</span>")
        else:
            links.append(f"<a href='{base_href}{sep}{param}={p}'>{p}</a>")
    if current_page < total_pages:
        links.append(f"<a href='{base_href}{sep}{param}={current_page + 1}'>›</a>")
    links.append(f"<span class='pg-info'>Page {current_page} of {total_pages}</span>")
    return f"<div class='pagination'>{''.join(links)}</div>"


def paginate(items: list, current_page: int, page_size: int = 25) -> tuple[list, int, int]:
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    current_page = max(1, min(current_page, total_pages))
    start = (current_page - 1) * page_size
    return items[start : start + page_size], current_page, total_pages
