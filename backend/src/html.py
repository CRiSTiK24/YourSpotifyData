import os
from contextvars import ContextVar
from html import escape
from urllib.parse import quote

from fastapi.responses import HTMLResponse

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)

logged_in_var: ContextVar[bool] = ContextVar("logged_in", default=False)


_SITE_NAME = "Your Spotify Data"


def _quick_search_widget(id_prefix: str) -> str:
    input_id = f"{id_prefix}-search-input"
    results_id = f"{id_prefix}-search-results"
    return f"""
    <div class="quick-search">
      <input id="{input_id}" class="quick-search-input" type="text" name="query" autocomplete="off"
        placeholder="Search…" aria-label="Search"
        hx-get="/search" hx-trigger="input changed delay:300ms" hx-target="#{results_id}"
        hx-select="unset" hx-swap="innerHTML">
      <div id="{results_id}" class="quick-search-results"></div>
    </div>"""


def page(content: str, title: str = "") -> HTMLResponse:
    page_title = f"{title} · {_SITE_NAME}" if title else _SITE_NAME
    if logged_in_var.get():
        sidebar_bottom = """
    <div class="sidebar-bottom">
      <a href="/upload">Upload</a>
      <a href="/scrobbler">Scrobbler</a>
      <a href="/theme">Theme</a>
    </div>"""
    else:
        sidebar_bottom = """
    <div class="sidebar-bottom">
      <a href="/login">Login</a>
    </div>"""
    nav_links = """
    <a href="/playlists">See my curated playlists!</a>
    <a href="/liked-albums">Albums I like</a>
    <hr class="sidebar-divider">
    <a href="/most-listened">My most listened</a>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
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
<body hx-boost="true" hx-target="#content" hx-select="#content" hx-swap="outerHTML transition:true">
<div class="shell">
  <aside class="sidebar">
    <a class="brand" href="/">Home</a>
    <hr class="sidebar-divider">{nav_links}{sidebar_bottom}
  </aside>

  <header class="mobile-topbar">
    <button type="button" class="hamburger-btn" id="hamburger-btn" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-drawer">
      <span></span><span></span><span></span>
    </button>
    {_quick_search_widget("topbar")}
  </header>

  <div class="drawer-overlay" id="drawer-overlay"></div>
  <nav class="mobile-drawer" id="mobile-drawer" aria-label="Main menu">
    <a class="brand" href="/">Home</a>
    <hr class="sidebar-divider">{nav_links}{sidebar_bottom}
  </nav>

  <div class="content-column">
    <header class="desktop-topbar">
      {_quick_search_widget("desktop")}
    </header>
    <main class="content" id="content">
{content}
    </main>
  </div>
</div>
<script src="/static/mobile-nav.js"></script>
<script src="/static/tooltips.js"></script>
<script src="/static/quick-search.js"></script>
<script src="/static/most-listened.js"></script>
</body>
</html>"""
    return HTMLResponse(html)


def link(label: str, href: str) -> str:
    return f"<a href='{escape(href)}'>{escape(label)}</a>"


def button(label: str, href: str, *, hx_boost: bool | None = None) -> str:
    boost_attr = f" hx-boost='{'true' if hx_boost else 'false'}'" if hx_boost is not None else ""
    return f"<a class='btn' href='{escape(href)}'{boost_attr}>{escape(label)}</a>"


def copy_list_button(lines: list[str], element_id: str, label: str = "Copy List") -> str:
    text = "\n".join(lines)
    id_esc = escape(element_id)
    label_esc = escape(label)
    return f"""
<pre id="{id_esc}" style="display:none">{escape(text)}</pre>
<button type="button" class="btn" onclick="navigator.clipboard.writeText(document.getElementById('{id_esc}').textContent).then(() => {{ this.textContent = 'Copied!'; setTimeout(() => {{ this.textContent = '{label_esc}'; }}, 1500); }})">{label_esc}</button>"""


def page_header(title: str, actions: str = "") -> str:
    return f"""
<div class="page-header">
  <h1>{escape(title)}</h1>
  {actions}
</div>"""


def search_form(
    action: str,
    placeholder: str,
    *,
    value: str = "",
    autofocus: bool = True,
    name: str = "query",
    hx_target: str = "#content",
    hx_select: str = "#content",
    hx_swap: str = "outerHTML",
    hx_push_url: bool = True,
) -> str:
    autofocus_attr = " autofocus" if autofocus else ""
    value_attr = f" value='{escape(value)}'" if value else ""
    action_esc = escape(action)
    push_url = "true" if hx_push_url else "false"
    return f"""
<form class="search-form" action="{action_esc}" method="get" autocomplete="off">
  <input id="live-search-input" name="{escape(name)}" type="text" autocomplete="off"{value_attr} placeholder="{escape(placeholder)}"{autofocus_attr}
    onkeydown="if(event.key==='Enter'){{event.preventDefault();}}"
    hx-get="{action_esc}" hx-trigger="input changed delay:300ms" hx-target="{escape(hx_target)}"
    hx-select="{escape(hx_select)}" hx-swap="{escape(hx_swap)}" hx-push-url="{push_url}" hx-preserve="true">
</form>"""


def _recolored_cover_src(
    image_url: str | None, size: int | None = None, *, raw: bool = False
) -> str | None:
    if not image_url:
        return None
    src = f"/cover?src={quote(image_url, safe='')}"
    if size:
        src += f"&size={size}"
    if raw:
        src += "&raw=true"
    return src


def row(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
    bar_fraction: float | None = None,
) -> str:
    cover_src = _recolored_cover_src(image_url, size=64)
    thumb = f"<img class='row-thumb' src='{escape(cover_src)}' loading='lazy'>" if cover_src else ""
    left = f"<a class='row-primary' href='{escape(primary_href)}'>{escape(primary_label)}</a>"
    if secondary_label and secondary_href:
        left += (
            f" <span class='sep'>—</span> "
            f"<a class='row-secondary' href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        )
    if bar_fraction is not None:
        fill_pct = max(0.0, min(1.0, bar_fraction)) * 100
        label = f"<span class='row-bar-label'>{escape(note)}</span>" if note else ""
        right = (
            f"<div class='row-bar-wrap'>"
            f"<div class='row-bar'><div class='row-bar-fill' style='width:{fill_pct:.1f}%'></div></div>"
            f"{label}</div>"
        )
    else:
        right = f"<span class='note'>{escape(note)}</span>" if note else ""
    return f"<div class='row'><div class='left'>{thumb}{left}</div>{right}</div>"


def card(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
    hover_tooltip: str | None = None,
    raw_cover: bool = False,
) -> str:
    cover_src = _recolored_cover_src(image_url, size=320, raw=raw_cover)
    thumb_class = "card-thumb card-thumb-raw" if raw_cover else "card-thumb"
    thumb = (
        f"<img class='{thumb_class}' src='{escape(cover_src)}' loading='lazy'>"
        if cover_src
        else "<div class='card-thumb card-thumb-empty'></div>"
    )
    secondary = (
        f"<a class='card-secondary' href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        if secondary_label and secondary_href
        else ""
    )
    note_html = f"<span class='card-note'>{escape(note)}</span>" if note else ""
    tooltip_attr = f" data-tooltip='{escape(hover_tooltip)}'" if hover_tooltip else ""
    info_btn = (
        "<button type='button' class='card-info-btn' aria-label='Show description'>i</button>"
        if hover_tooltip
        else ""
    )
    return f"""
<div class="card"{tooltip_attr}>
  <a class="card-cover" href="{escape(primary_href)}">{thumb}</a>
  {info_btn}
  <a class="card-title" href="{escape(primary_href)}">{escape(primary_label)}</a>
  {secondary}
  {note_html}
</div>"""


def grid(cards_html: str, *, compact: bool = False) -> str:
    cls = "grid grid-compact" if compact else "grid"
    return f"<div class='{cls}'>{cards_html}</div>"


def hero_image(image_url: str | None, *, raw: bool = False) -> str:
    cover_src = _recolored_cover_src(image_url, size=320, raw=raw)
    if not cover_src:
        return ""
    cls = "hero-image hero-image-raw" if raw else "hero-image"
    return f"<img class='{cls}' src='{escape(cover_src)}' loading='lazy'>"


def filter_clear_link(label: str, clear_href: str) -> str:
    return (
        f" &nbsp;·&nbsp; <a class='detail-filter-clear' href='{escape(clear_href)}'>"
        f"{escape(label)} <span class='detail-filter-clear-x'>&times;</span></a>"
    )


def detail_header(title_html: str, meta_html: str, hero_html: str, heatmap_html: str) -> str:
    return f"""
<div class="detail-header-top">
  <div class="detail-header-title">
    {title_html}
    {meta_html}
  </div>
  <div class="detail-header-media">
    {hero_html}
    <div class="detail-header-heatmap">{heatmap_html}</div>
  </div>
</div>"""


def detail_layout(
    header: str,
    list_title: str,
    list_content: str,
    list_id: str = "",
    list_actions: str = "",
) -> str:
    list_id_attr = f" id='{escape(list_id)}'" if list_id else ""
    return f"""
<div class="detail-layout">
  <div class="panel detail-header">
    {header}
    <hr class="divider">
    <div class="list-title-row">
      <h2>{escape(list_title)}</h2>
      {list_actions}
    </div>
    <div{list_id_attr}>{list_content}</div>
  </div>
</div>"""


def infinite_scroll_trigger(next_href: str) -> str:
    return (
        f"<div hx-get='{escape(next_href)}' hx-trigger='intersect once' hx-target='this' "
        f"hx-select='unset' hx-swap='outerHTML'></div>"
    )


def paginated_fragment(
    rows_html: str, *, offset: int, has_more: bool, next_href: str, empty_message: str = ""
) -> str:
    if not rows_html:
        return empty_message if offset == 0 else ""
    if has_more:
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def lazy_load_trigger(href: str, label: str = "Loading…") -> str:
    return (
        f"<p class='info' hx-get='{escape(href)}' hx-trigger='load' hx-target='this' "
        f"hx-select='unset' hx-swap='outerHTML'>{escape(label)}</p>"
    )
