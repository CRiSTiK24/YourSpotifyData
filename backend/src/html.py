import colorsys
import math
import os
from collections.abc import Callable
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
  <link rel="preload" href="/static/fonts/degheest/Director-Variable.woff2" as="font" type="font/woff2" crossorigin>
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
    <main class="content" id="content">
{content}
    </main>
  </div>

  <div class="preview-bar" id="preview-bar" hidden>
    <button type="button" class="preview-btn preview-bar-toggle" id="preview-bar-toggle" aria-label="Pause">
      <span class="preview-icon" id="preview-bar-toggle-icon">&#10074;&#10074;</span>
    </button>
    <div class="preview-bar-info">
      <span class="preview-bar-track" id="preview-bar-track"></span>
      <span class="preview-bar-sep">—</span>
      <span class="preview-bar-artist" id="preview-bar-artist"></span>
    </div>
    <div class="preview-bar-progress" id="preview-bar-progress"><div class="preview-bar-progress-fill" id="preview-bar-fill"></div></div>
    <input type="range" class="preview-bar-volume" id="preview-bar-volume" min="0" max="1" step="0.01" aria-label="Volume">
  </div>
</div>
<script src="/static/mobile-nav.js"></script>
<script src="/static/tooltips.js"></script>
<script src="/static/quick-search.js"></script>
<script src="/static/most-listened.js"></script>
<script src="/static/preview.js"></script>
<script src="/static/carousel.js"></script>
</body>
</html>"""
    return HTMLResponse(html)


def link(label: str, href: str) -> str:
    return f"<a href='{escape(href)}'>{escape(label)}</a>"


def button(label: str, href: str, *, hx_boost: bool | None = None) -> str:
    boost_attr = f" hx-boost='{'true' if hx_boost else 'false'}'" if hx_boost is not None else ""
    return f"<a class='btn' href='{escape(href)}'{boost_attr}>{escape(label)}</a>"


def spotify_open_button(open_url: str) -> str:
    return (
        f"<a class='btn' style='margin-left:auto' href='{escape(open_url)}' "
        "target='_blank' rel='noopener noreferrer'>Open in Spotify</a>"
    )


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


def preview_play_button(track_name: str, preview_artist: str | None, extra_class: str) -> str:
    if not preview_artist:
        return ""
    return (
        f"<button type='button' class='preview-btn {extra_class}' aria-label='Play preview' "
        f"data-preview-track='{escape(track_name)}' data-preview-artist='{escape(preview_artist)}'>"
        f"<span class='preview-icon'>&#9654;</span></button>"
    )


def row(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
    bar_fraction: float | None = None,
    preview_artist: str | None = None,
) -> str:
    cover_src = _recolored_cover_src(image_url, size=64)
    thumb = f"<img class='row-thumb' src='{escape(cover_src)}' loading='lazy'>" if cover_src else ""
    play_btn = preview_play_button(primary_label, preview_artist, "row-play-btn")
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
    return f"<div class='row'><div class='left'>{play_btn}{thumb}{left}</div>{right}</div>"


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
    preview_artist: str | None = None,
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
    play_btn = preview_play_button(primary_label, preview_artist, "card-play-btn")
    return f"""
<div class="card"{tooltip_attr}>
  <div class="card-cover-wrap">
    <a class="card-cover" href="{escape(primary_href)}">{thumb}</a>
    {play_btn}
  </div>
  {info_btn}
  <a class="card-title" href="{escape(primary_href)}">{escape(primary_label)}</a>
  {secondary}
  {note_html}
</div>"""


def grid(cards_html: str, *, compact: bool = False) -> str:
    cls = "grid grid-compact" if compact else "grid"
    return f"<div class='{cls}'>{cards_html}</div>"


def carousel(cards_html: str, *, compact: bool = False) -> str:
    cls = "carousel carousel-compact" if compact else "carousel"
    return f"<div class='{cls}'>{cards_html}</div>"


def word_cloud(
    items: list[tuple[str, int]],
    *,
    min_size: int = 14,
    max_size: int = 40,
    href_for: Callable[[str], str] | None = None,
    active: set[str] | None = None,
    extra_class: str = "",
    hx_swap_target: str = "",
    container_id: str = "",
    oob: bool = False,
) -> str:
    if not items:
        return ""
    # Hues are assigned by alphabetical rank (not display order) and evenly
    # spaced around the wheel, so any two labels always sit far apart in hue
    # regardless of how many share similar play counts, and a given label's
    # color stays roughly stable across re-renders instead of reshuffling
    # whenever its count (and therefore sort position) changes.
    by_name = sorted({name for name, _ in items})
    hue_step = 360 / len(by_name)
    hues = {name: idx * hue_step for idx, name in enumerate(by_name)}

    counts = [count for _, count in items]
    lo, hi = math.log(min(counts) + 1), math.log(max(counts) + 1)
    span = hi - lo or 1

    tags = []
    for name, count in sorted(items, key=lambda item: item[1], reverse=True):
        t = (math.log(count + 1) - lo) / span
        size = min_size + t * (max_size - min_size)
        r, g, b = colorsys.hls_to_rgb(hues[name] / 360, 0.68, 0.62)
        color = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
        plural = "" if count == 1 else "s"
        title = f"{escape(name)} · {count} play{plural}"
        is_active = active is not None and name in active
        tag_class = "word-cloud-tag active" if is_active else "word-cloud-tag"
        # var(--wc-scale, 1) lets CSS shrink every tag proportionally at
        # narrow viewports (see .widget .word-cloud.carousel's mobile
        # override) without losing the size-hierarchy this px value
        # already encodes relative to the other tags.
        style = f"font-size:calc({size:.1f}px * var(--wc-scale, 1));color:{color}"
        if href_for:
            href = escape(href_for(name))
            # hx-get re-requests this same href but only swaps/selects
            # hx_swap_target's subtree from the response instead of the
            # full #content htmx's global hx-boost would otherwise swap
            # (see CLAUDE.md's hx-boost override gotcha) - href itself is
            # left as a real link, so this degrades to a normal full
            # navigation with JS disabled.
            hx_attrs = (
                f" hx-get='{href}' hx-target='#{hx_swap_target}' hx-select='#{hx_swap_target}' "
                f"hx-swap='outerHTML' hx-push-url='true'"
                if hx_swap_target
                else ""
            )
            tags.append(
                f"<a class='{tag_class}' href='{href}' style='{style}'{hx_attrs} "
                f"title='{title}'>{escape(name)}</a>"
            )
        else:
            tags.append(
                f"<span class='{tag_class}' style='{style}' title='{title}'>{escape(name)}</span>"
            )
    cls = f"word-cloud {extra_class}" if extra_class else "word-cloud"
    id_attr = f" id='{escape(container_id)}'" if container_id else ""
    # hx-swap-oob="innerHTML" (rather than the default outerHTML) replaces
    # only the <a> tags inside this element, not the element itself - the
    # carousel div's own scrollLeft lives on that element, so leaving it
    # in place (only its children swap) is what keeps the carousel from
    # jumping back to the start on every genre click, even though this
    # fragment rides along in every /most-listened response regardless of
    # which genre (if any) triggered it.
    oob_attr = " hx-swap-oob='innerHTML'" if oob else ""
    return f"<div class='{cls}'{id_attr}{oob_attr}>{''.join(tags)}</div>"


def widget_grid(widgets_html: str) -> str:
    return f"<div class='widget-grid'>{widgets_html}</div>"


def widget(
    title: str,
    content_html: str,
    *,
    info_tooltip: str | None = None,
) -> str:
    tooltip_attr = f" data-tooltip='{escape(info_tooltip)}'" if info_tooltip else ""
    info_btn = (
        f"<button type='button' class='info-btn' aria-label='About this widget'"
        f"{tooltip_attr}>i</button>"
        if info_tooltip
        else ""
    )
    title_html = (
        f"""<div class="widget-header"><h2>{escape(title)}</h2>{info_btn}</div>"""
        if title
        else info_btn
    )
    return f"""
<div class="widget">
  {title_html}
  {content_html}
</div>"""


def hero_image(image_url: str | None, *, raw: bool = False, large: bool = False) -> str:
    cover_src = _recolored_cover_src(image_url, size=320, raw=raw)
    if not cover_src:
        return ""
    classes = "hero-image"
    if raw:
        classes += " hero-image-raw"
    if large:
        classes += " hero-image-large"
    return f"<img class='{classes}' src='{escape(cover_src)}' loading='lazy'>"


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
  {hero_html}
  <div class="detail-header-heatmap">{heatmap_html}</div>
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
    # 'intersect once' does the loading automatically as this scrolls into
    # view, but it's a real fallback, not decoration: some of these sit
    # inside their own independently-scrolling container (e.g. .ml-column
    # on desktop, not the page itself), and scrolling the wrong element
    # never brings an invisible sentinel into view - 'click' on the same
    # element means there's always a visible, working way to load more
    # even if the automatic trigger never fires for whatever reason.
    return (
        f"<button type='button' class='infinite-scroll-trigger' "
        f"hx-get='{escape(next_href)}' hx-trigger='intersect once, click' hx-target='this' "
        f"hx-select='unset' hx-swap='outerHTML'>Load more</button>"
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
