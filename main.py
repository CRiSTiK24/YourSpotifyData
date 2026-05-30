import calendar
import os
import sqlite3
from collections import defaultdict
from urllib.parse import urlencode

import streamlit as st

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "data", "spotifyProcessed", "SpotifyData.db")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _word_clauses(words, *columns):
    parts = []
    params = []
    for word in words:
        col_checks = " OR ".join(f"{col} LIKE ?" for col in columns)
        parts.append(f"({col_checks})")
        params.extend(f"%{word}%" for _ in columns)
    return " AND ".join(parts), params


def search_track_history(con, query):
    words = query.split()
    where, params = _word_clauses(words, "name", "singer")
    return con.execute(
        f"SELECT name, singer, time FROM track_history WHERE {where} ORDER BY time DESC",
        params,
    ).fetchall()


def search_library_tracks(con, query):
    words = query.split()
    where, params = _word_clauses(words, "track_name", "artist_name")
    return con.execute(
        f"SELECT track_name, artist_name FROM library_tracks WHERE {where}",
        params,
    ).fetchall()


def search_library_albums(con, query):
    words = query.split()
    where, params = _word_clauses(words, "album_name", "artist_name")
    return con.execute(
        f"SELECT album_name, artist_name FROM library_albums WHERE {where}",
        params,
    ).fetchall()


def search_playlists(con, query):
    words = query.split()
    where, params = _word_clauses(words, "pt.track_name", "pt.artist_name")
    return con.execute(
        f"""
        SELECT pt.track_name, pt.artist_name, p.name AS playlist_name
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        WHERE {where}
        ORDER BY p.name
        """,
        params,
    ).fetchall()


# ── navigation helpers ────────────────────────────────────────────────────────

def nav(page, **kwargs):
    st.query_params.clear()
    st.query_params["page"] = page
    for k, v in kwargs.items():
        st.query_params[k] = str(v)
    st.rerun()


def _url(**kwargs):
    return "?" + urlencode(kwargs)


def _link(label, **kwargs):
    url = _url(**kwargs)
    return f"<a href='{url}' target='_self' style='color:#58a6ff;text-decoration:none'>{label}</a>"


def _row(primary_label, primary_kwargs, secondary_label=None, secondary_kwargs=None, note=None):
    """Render a clean text row with one or two links and an optional right-side note."""
    primary = _link(primary_label, **primary_kwargs)
    parts = [primary]
    if secondary_label and secondary_kwargs:
        secondary = _link(secondary_label, **secondary_kwargs)
        parts.append(f"<span style='color:#8b949e'> — </span>{secondary}")
    right = f"<span style='float:right;color:#8b949e;font-size:0.85em'>{note}</span>" if note else ""
    st.markdown(
        f"<div style='padding:4px 0;border-bottom:1px solid #21262d'>{right}{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def back_button(label="← Back"):
    if st.button(label):
        nav("home")


# ── data loaders ──────────────────────────────────────────────────────────────

def load_library_tracks(con):
    return con.execute(
        """
        SELECT lt.track_name, lt.artist_name, MAX(th.time) as last_played
        FROM library_tracks lt
        LEFT JOIN track_history th ON th.name = lt.track_name AND th.singer = lt.artist_name
        GROUP BY lt.track_name, lt.artist_name
        ORDER BY last_played DESC NULLS LAST
        """
    ).fetchall()


def load_library_albums(con):
    return con.execute(
        "SELECT album_name, artist_name FROM library_albums ORDER BY artist_name, album_name"
    ).fetchall()


def load_playlists(con):
    return con.execute(
        "SELECT id, name FROM playlists ORDER BY name"
    ).fetchall()


def load_playlist_tracks(con, playlist_id):
    return con.execute(
        "SELECT track_name, artist_name FROM playlist_tracks WHERE playlist_id = ? ORDER BY rowid",
        (playlist_id,),
    ).fetchall()


def load_track_history(con, track_name, artist_name):
    return con.execute(
        "SELECT name, singer, album, time FROM track_history WHERE name = ? AND (singer = ? OR singer IS NULL) ORDER BY time DESC",
        (track_name, artist_name),
    ).fetchall()


def load_playlist_history(con, playlist_id):
    return con.execute(
        """
        SELECT th.name, th.singer, th.time
        FROM track_history th
        JOIN playlist_tracks pt ON th.name = pt.track_name AND th.singer = pt.artist_name
        WHERE pt.playlist_id = ?
        ORDER BY th.time DESC
        """,
        (playlist_id,),
    ).fetchall()


def load_artists(con):
    return con.execute(
        """
        SELECT singer, COUNT(*) as play_count
        FROM track_history
        WHERE singer IS NOT NULL AND singer != ''
        GROUP BY singer
        ORDER BY play_count DESC
        """
    ).fetchall()


def load_artist_history(con, artist_name):
    return con.execute(
        "SELECT name, singer, time FROM track_history WHERE singer = ? ORDER BY time DESC",
        (artist_name,),
    ).fetchall()


def load_album_track_history(con, album_name, artist_name):
    return con.execute(
        """
        SELECT th.name, th.singer, th.time
        FROM track_history th
        WHERE th.album = ?
        ORDER BY th.time DESC
        """,
        (album_name,),
    ).fetchall()


# ── heatmap ───────────────────────────────────────────────────────────────────

COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _cell_color(count, max_count):
    if count == 0 or max_count == 0:
        return COLORS[0]
    idx = max(1, round(count / max_count * 4))
    return COLORS[idx]


def _legend_html():
    squares = "".join(
        f'<span style="display:inline-block;width:14px;height:14px;background:{c};border-radius:2px;margin-right:3px"></span>'
        for c in COLORS
    )
    return (
        f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:6px;font-size:12px;color:#8b949e">'
        f'Less &nbsp;{squares}&nbsp; More</div>'
    )


def _render_month_grid(counts, years, selected, base_params, key_prefix):
    header = "<th style='width:40px'></th>" + "".join(
        f"<th style='width:44px;text-align:center;font-size:11px;color:#8b949e'>{m}</th>"
        for m in MONTHS
    )
    max_count = max(counts.values()) if counts else 1
    rows_html = ""
    for year in years:
        cells = f"<td style='font-size:11px;color:#8b949e;padding-right:6px'>{year}</td>"
        for m in range(1, 13):
            c = counts.get((year, m), 0)
            color = _cell_color(c, max_count)
            border = "2px solid #e6edf3" if selected == (year, m) else "2px solid transparent"
            tooltip = f"{MONTHS[m-1]} {year}: {c} play{'s' if c != 1 else ''}"
            # clicking a month clears the day selection
            cell_params = {**base_params, f"hm_{key_prefix}": f"{year}-{m}"}
            qs = urlencode(cell_params)
            cells += (
                f"<td style='padding:2px'>"
                f"<a href='?{qs}' target='_self' title='{tooltip}' style='display:block;width:32px;height:32px;"
                f"background:{color};border-radius:4px;border:{border};text-align:center;"
                f"line-height:32px;font-size:11px;color:#e6edf3;text-decoration:none'>"
                f"{'&nbsp;' if c == 0 else c}</a></td>"
            )
        rows_html += f"<tr>{cells}</tr>"
    table = (
        f"<table style='border-collapse:separate;border-spacing:2px;background:#0d1117;padding:8px;border-radius:6px'>"
        f"<thead><tr>{header}</tr></thead><tbody>{rows_html}</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


def _render_day_grid(year, month, day_counts, selected_day, base_params, key_prefix):
    max_count = max(day_counts.values()) if day_counts else 1
    # find weekday of 1st (Monday=0)
    first_weekday, num_days = calendar.monthrange(year, month)

    header = "<th style='width:30px'></th>" + "".join(
        f"<th style='width:38px;text-align:center;font-size:11px;color:#8b949e'>{d}</th>"
        for d in DAYS_OF_WEEK
    )

    # build grid: pad with empty cells before day 1
    day_cursor = 1
    rows_html = ""
    week = 1
    while day_cursor <= num_days:
        cells = f"<td style='font-size:11px;color:#8b949e;padding-right:4px'>W{week}</td>"
        for dow in range(7):
            if (week == 1 and dow < first_weekday) or day_cursor > num_days:
                cells += "<td style='padding:2px'><span style='display:block;width:28px;height:28px'></span></td>"
            else:
                d = day_cursor
                c = day_counts.get(d, 0)
                color = _cell_color(c, max_count)
                border = "2px solid #e6edf3" if selected_day == d else "2px solid transparent"
                tooltip = f"{MONTHS[month-1]} {d}, {year}: {c} play{'s' if c != 1 else ''}"
                cell_params = {**base_params, f"hm_{key_prefix}": f"{year}-{month}", f"hm_{key_prefix}_d": str(d)}
                qs = urlencode(cell_params)
                cells += (
                    f"<td style='padding:2px'>"
                    f"<a href='?{qs}' target='_self' title='{tooltip}' style='display:block;width:28px;height:28px;"
                    f"background:{color};border-radius:4px;border:{border};text-align:center;"
                    f"line-height:28px;font-size:10px;color:#e6edf3;text-decoration:none'>"
                    f"{'&nbsp;' if c == 0 else c}</a></td>"
                )
                day_cursor += 1
                if day_cursor > num_days:
                    # fill remaining cells in last row
                    for _ in range(dow + 1, 6):
                        cells += "<td style='padding:2px'><span style='display:block;width:28px;height:28px'></span></td>"
                    break
        rows_html += f"<tr>{cells}</tr>"
        week += 1

    table = (
        f"<table style='border-collapse:separate;border-spacing:2px;background:#0d1117;padding:8px;border-radius:6px'>"
        f"<thead><tr>{header}</tr></thead><tbody>{rows_html}</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


def build_heatmap(history, key_prefix):
    counts: dict[tuple, int] = defaultdict(int)
    by_month: dict[tuple, list] = defaultdict(list)

    for row in history:
        ts = row["time"]
        year, month, day = int(ts[:4]), int(ts[5:7]), int(ts[8:10])
        counts[(year, month)] += 1
        entry = {"day": day}
        if "name" in row.keys():
            entry["name"] = row["name"]
            entry["singer"] = row["singer"]
        by_month[(year, month)].append(entry)

    if not counts:
        st.info("No play history to display.")
        return None

    years = sorted({y for y, _ in counts})
    qp = st.query_params
    base_params = {k: v for k, v in qp.items() if not k.startswith("hm_")}

    # --- month grid ---
    sel_month_key = qp.get(f"hm_{key_prefix}", "")
    sel_month = tuple(int(x) for x in sel_month_key.split("-")) if sel_month_key else None

    st.markdown(_legend_html(), unsafe_allow_html=True)

    if not sel_month:
        _render_month_grid(counts, years, sel_month, base_params, key_prefix)
        return None

    sel_year, sel_month_num = sel_month
    month_plays = by_month.get((sel_year, sel_month_num), [])

    day_counts: dict[int, int] = defaultdict(int)
    by_day: dict[int, list] = defaultdict(list)
    for p in month_plays:
        day_counts[p["day"]] += 1
        by_day[p["day"]].append(p)

    sel_day_key = qp.get(f"hm_{key_prefix}_d", "")
    sel_day = int(sel_day_key) if sel_day_key else None

    # --- side by side ---
    col_month, col_day = st.columns([2, 1], gap="large")
    with col_month:
        _render_month_grid(counts, years, sel_month, base_params, key_prefix)
    with col_day:
        st.markdown(
            f"<div style='font-size:13px;color:#8b949e;margin-bottom:6px'>"
            f"{MONTHS[sel_month_num-1]} {sel_year} — {len(month_plays)} play{'s' if len(month_plays) != 1 else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )
        _render_day_grid(sel_year, sel_month_num, day_counts, sel_day, base_params, key_prefix)

    if sel_day:
        return sel_year, sel_month_num, sel_day, by_day.get(sel_day, [])
    return sel_year, sel_month_num, None, month_plays


# ── helpers ──────────────────────────────────────────────────────────────────

def _aggregate_plays(plays):
    """Return list of (name, singer, count) sorted by count descending."""
    counts: dict[tuple, int] = defaultdict(int)
    for p in plays:
        counts[(p.get("name", ""), p.get("singer", ""))] += 1
    return sorted(
        [(name, singer, count) for (name, singer), count in counts.items()],
        key=lambda x: -x[2],
    )


# ── pages ─────────────────────────────────────────────────────────────────────

def page_home(con):
    st.title("🎵 Your Spotify Data")

    search_query = st.text_input("Search for a song or artist", placeholder="e.g. yellow coldplay", on_change=None)
    if search_query:
        nav("search", query=search_query)

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        n = con.execute("SELECT COUNT(*) FROM library_tracks").fetchone()[0]
        st.subheader("💚 Liked Songs")
        st.caption(f"{n} tracks")
        if st.button("View Liked Songs", key="home_liked_songs"):
            nav("liked_songs")

    with col2:
        n = con.execute("SELECT COUNT(*) FROM library_albums").fetchone()[0]
        st.subheader("💿 Liked Albums")
        st.caption(f"{n} albums")
        if st.button("View Liked Albums", key="home_liked_albums"):
            nav("liked_albums")

    with col3:
        n = con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        st.subheader("📋 Playlists")
        st.caption(f"{n} playlists")
        if st.button("View Playlists", key="home_playlists"):
            nav("playlists")

    with col4:
        n = con.execute("SELECT COUNT(DISTINCT singer) FROM track_history WHERE singer IS NOT NULL AND singer != ''").fetchone()[0]
        st.subheader("🎤 Artists")
        st.caption(f"{n} artists")
        if st.button("View Artists", key="home_artists"):
            nav("artists")


def page_liked_songs(con):
    back_button()
    tracks = load_library_tracks(con)
    st.title(f"💚 Liked Songs ({len(tracks)})")
    st.divider()
    for t in tracks:
        _row(
            t["track_name"], dict(page="track_detail", track_name=t["track_name"], artist_name=t["artist_name"]),
            t["artist_name"], dict(page="artist_detail", artist_name=t["artist_name"]),
        )


def page_liked_albums(con):
    back_button()
    albums = load_library_albums(con)
    st.title(f"💿 Liked Albums ({len(albums)})")
    st.divider()
    for a in albums:
        _row(
            a["album_name"], dict(page="album_detail", album_name=a["album_name"], artist_name=a["artist_name"]),
            a["artist_name"], dict(page="artist_detail", artist_name=a["artist_name"]),
        )


def page_playlists(con):
    back_button()
    playlists = load_playlists(con)
    st.title(f"📋 Playlists ({len(playlists)})")
    st.divider()
    for pl in playlists:
        _row(pl["name"], dict(page="playlist_detail", playlist_id=pl["id"], playlist_name=pl["name"]))


def page_search(con, query):
    back_button()
    st.title(f'Search: "{query}"')

    history = search_track_history(con, query)

    # ── aggregated play history with heatmap ──────────────────────────────────
    aggregated = _aggregate_plays([{"name": r["name"], "singer": r["singer"], "day": int(r["time"][8:10])} for r in history])
    st.subheader(f"🎵 Play history — {len(history)} plays across {len(aggregated)} track{'s' if len(aggregated) != 1 else ''}")

    if history:
        page_size = 25
        current_page = int(st.query_params.get("search_page", 1))
        total_pages = max(1, (len(aggregated) + page_size - 1) // page_size)
        current_page = max(1, min(current_page, total_pages))
        start = (current_page - 1) * page_size
        end = start + page_size

        for name, singer, count in aggregated[start:end]:
            _row(
                name, dict(page="track_detail", track_name=name, artist_name=singer or ""),
                singer, dict(page="artist_detail", artist_name=singer) if singer else None,
                note=f"×{count}",
            )

        if total_pages > 1:
            # show up to 9 page numbers centred around current page
            half = 4
            p_start = max(1, current_page - half)
            p_end = min(total_pages, p_start + 8)
            p_start = max(1, p_end - 8)

            links = []
            if current_page > 1:
                links.append(f"<a href='{_url(page='search', query=query, search_page=current_page-1)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>‹</a>")
            for p in range(p_start, p_end + 1):
                if p == current_page:
                    links.append(f"<span style='padding:4px 8px;background:#21262d;border-radius:4px;color:#e6edf3'>{p}</span>")
                else:
                    links.append(f"<a href='{_url(page='search', query=query, search_page=p)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>{p}</a>")
            if current_page < total_pages:
                links.append(f"<a href='{_url(page='search', query=query, search_page=current_page+1)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>›</a>")

            st.markdown(
                f"<div style='display:flex;align-items:center;gap:2px;margin-top:12px'>{''.join(links)}"
                f"<span style='color:#8b949e;font-size:0.85em;margin-left:12px'>Page {current_page} of {total_pages}</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown("**Listen history heatmap**")
        build_heatmap(history, key_prefix=f"search_{query}")
    else:
        st.info("No play history found.")

    st.divider()

    # ── liked songs ───────────────────────────────────────────────────────────
    lib_tracks = search_library_tracks(con, query)
    st.subheader(f"💚 Liked songs ({len(lib_tracks)})")
    if lib_tracks:
        for row in lib_tracks:
            _row(
                row["track_name"], dict(page="track_detail", track_name=row["track_name"], artist_name=row["artist_name"]),
                row["artist_name"], dict(page="artist_detail", artist_name=row["artist_name"]),
            )
    else:
        st.info("Not in your liked songs.")

    # ── liked albums ──────────────────────────────────────────────────────────
    lib_albums = search_library_albums(con, query)
    if lib_albums:
        st.subheader(f"💿 Liked albums ({len(lib_albums)})")
        for row in lib_albums:
            _row(
                row["album_name"], dict(page="album_detail", album_name=row["album_name"], artist_name=row["artist_name"]),
                row["artist_name"], dict(page="artist_detail", artist_name=row["artist_name"]),
            )

    st.divider()

    # ── playlists ─────────────────────────────────────────────────────────────
    playlist_rows = search_playlists(con, query)
    st.subheader(f"📋 Playlists ({len(playlist_rows)} matches)")
    if playlist_rows:
        by_playlist: dict[str, dict] = {}
        for row in playlist_rows:
            by_playlist.setdefault(row["playlist_name"], {"id": None, "tracks": []})
            by_playlist[row["playlist_name"]]["tracks"].append(row)
        pl_ids = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM playlists").fetchall()}
        for pl_name, data in by_playlist.items():
            pl_id = pl_ids.get(pl_name)
            with st.expander(f"📋 {pl_name} ({len(data['tracks'])} match{'es' if len(data['tracks']) > 1 else ''})"):
                if pl_id:
                    _row(f"Open {pl_name}", dict(page="playlist_detail", playlist_id=pl_id, playlist_name=pl_name))
                for t in data["tracks"]:
                    _row(
                        t["track_name"], dict(page="track_detail", track_name=t["track_name"], artist_name=t["artist_name"]),
                        t["artist_name"], dict(page="artist_detail", artist_name=t["artist_name"]),
                    )
    else:
        st.info("Not found in any playlist.")


def page_track_detail(con, track_name, artist_name):
    back_button()
    st.title(f"🎵 {track_name}")

    col_artist, col_album = st.columns([2, 3])
    with col_artist:
        if st.button(f"🎤 {artist_name}", key="track_to_artist"):
            nav("artist_detail", artist_name=artist_name)

    history = load_track_history(con, track_name, artist_name)
    st.markdown(f"**Played {len(history)} time{'s' if len(history) != 1 else ''}**")

    album_name = next((row["album"] for row in history if row["album"]), None)
    with col_album:
        if album_name:
            if st.button(f"💿 {album_name}", key="track_to_album"):
                nav("album_detail", album_name=album_name, artist_name=artist_name)

    st.divider()

    build_heatmap(history, key_prefix=f"track_{track_name}")

    st.divider()

    playlists = con.execute(
        """
        SELECT p.id, p.name FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        WHERE pt.track_name = ? AND pt.artist_name = ?
        """,
        (track_name, artist_name),
    ).fetchall()

    if playlists:
        st.subheader(f"📋 In {len(playlists)} playlist{'s' if len(playlists) != 1 else ''}")
        for pl in playlists:
            _row(pl["name"], dict(page="playlist_detail", playlist_id=pl["id"], playlist_name=pl["name"]))
    else:
        st.subheader("📋 Playlists")
        st.info("Not in any playlist.")


def page_album_detail(con, album_name, artist_name):
    back_button()
    st.title(f"💿 {album_name}")
    if st.button(f"🎤 {artist_name}", key="album_to_artist"):
        nav("artist_detail", artist_name=artist_name)

    history = load_album_track_history(con, album_name, artist_name)
    st.markdown(f"**{len(history)} plays from this album**")

    st.divider()

    result = build_heatmap(history, key_prefix=f"album_{album_name}")
    if result:
        year, month, day, plays = result
        label = f"{MONTHS[month-1]} {day}, {year}" if day else f"{MONTHS[month-1]} {year}"
        aggregated = _aggregate_plays(plays)
        st.subheader(f"{label} — {len(plays)} play{'s' if len(plays) != 1 else ''} across {len(aggregated)} track{'s' if len(aggregated) != 1 else ''}")
        for name, singer, count in aggregated:
            _row(
                name, dict(page="track_detail", track_name=name, artist_name=singer or artist_name),
                singer or artist_name, dict(page="artist_detail", artist_name=singer or artist_name),
                note=f"×{count}",
            )

    st.divider()

    st.subheader("All plays")
    for row in history:
        ts = row["time"].replace("T", " ").replace("Z", " UTC")
        _row(
            row["name"], dict(page="track_detail", track_name=row["name"], artist_name=row["singer"] or artist_name),
            note=ts,
        )


def page_playlist_detail(con, playlist_id, playlist_name):
    back_button()
    tracks = load_playlist_tracks(con, playlist_id)
    st.title(f"📋 {playlist_name}")
    st.markdown(f"**{len(tracks)} track{'s' if len(tracks) != 1 else ''}**")

    st.divider()

    history = load_playlist_history(con, playlist_id)
    st.markdown(f"**{len(history)} total plays across all tracks**")
    result = build_heatmap(history, key_prefix=f"playlist_{playlist_id}")
    if result:
        year, month, day, plays = result
        label = f"{MONTHS[month-1]} {day}, {year}" if day else f"{MONTHS[month-1]} {year}"
        aggregated = _aggregate_plays(plays)
        st.subheader(f"{label} — {len(plays)} play{'s' if len(plays) != 1 else ''} across {len(aggregated)} track{'s' if len(aggregated) != 1 else ''}")
        for name, singer, count in aggregated:
            _row(
                name, dict(page="track_detail", track_name=name, artist_name=singer or ""),
                singer, dict(page="artist_detail", artist_name=singer) if singer else None,
                note=f"×{count}",
            )

    st.divider()

    st.subheader("Tracks")
    for t in tracks:
        _row(
            t["track_name"], dict(page="track_detail", track_name=t["track_name"], artist_name=t["artist_name"]),
            t["artist_name"], dict(page="artist_detail", artist_name=t["artist_name"]),
        )


def page_artists(con):
    back_button()
    st.title("🎤 Artists")
    query = st.text_input("Search artists", placeholder="Type an artist name…")

    if query:
        words = query.split()
        where, params = _word_clauses(words, "singer")
        artists = con.execute(
            f"SELECT singer, COUNT(*) as play_count FROM track_history WHERE singer IS NOT NULL AND singer != '' AND {where} GROUP BY singer ORDER BY play_count DESC",
            params,
        ).fetchall()
    else:
        artists = con.execute(
            "SELECT singer, COUNT(*) as play_count FROM track_history WHERE singer IS NOT NULL AND singer != '' GROUP BY singer ORDER BY play_count DESC"
        ).fetchall()

    st.divider()

    page_size = 25
    current_page = int(st.query_params.get("artists_page", 1))
    total_pages = max(1, (len(artists) + page_size - 1) // page_size)
    current_page = max(1, min(current_page, total_pages))
    start = (current_page - 1) * page_size
    end = start + page_size

    for a in artists[start:end]:
        _row(a["singer"], dict(page="artist_detail", artist_name=a["singer"]), note=f"{a['play_count']} plays")

    if total_pages > 1:
        half = 4
        p_start = max(1, current_page - half)
        p_end = min(total_pages, p_start + 8)
        p_start = max(1, p_end - 8)

        links = []
        base = dict(page="artists")
        if query:
            base["artists_query"] = query
        if current_page > 1:
            links.append(f"<a href='{_url(**base, artists_page=current_page-1)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>‹</a>")
        for p in range(p_start, p_end + 1):
            if p == current_page:
                links.append(f"<span style='padding:4px 8px;background:#21262d;border-radius:4px;color:#e6edf3'>{p}</span>")
            else:
                links.append(f"<a href='{_url(**base, artists_page=p)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>{p}</a>")
        if current_page < total_pages:
            links.append(f"<a href='{_url(**base, artists_page=current_page+1)}' target='_self' style='color:#58a6ff;text-decoration:none;padding:4px 8px'>›</a>")

        st.markdown(
            f"<div style='display:flex;align-items:center;gap:2px;margin-top:12px'>{''.join(links)}"
            f"<span style='color:#8b949e;font-size:0.85em;margin-left:12px'>Page {current_page} of {total_pages} — {len(artists)} artists</span></div>",
            unsafe_allow_html=True,
        )


def page_artist_detail(con, artist_name):
    back_button()
    st.title(f"🎤 {artist_name}")

    history = load_artist_history(con, artist_name)
    st.markdown(f"**{len(history)} total plays**")

    st.divider()

    result = build_heatmap(history, key_prefix=f"artist_{artist_name}")
    if result:
        year, month, day, plays = result
        label = f"{MONTHS[month-1]} {day}, {year}" if day else f"{MONTHS[month-1]} {year}"
        aggregated = _aggregate_plays(plays)
        st.subheader(f"{label} — {len(plays)} play{'s' if len(plays) != 1 else ''} across {len(aggregated)} track{'s' if len(aggregated) != 1 else ''}")
        for name, singer, count in aggregated:
            _row(name, dict(page="track_detail", track_name=name, artist_name=artist_name), note=f"×{count}")

    st.divider()

    top_tracks = con.execute(
        "SELECT name, COUNT(*) as cnt FROM track_history WHERE singer = ? GROUP BY name ORDER BY cnt DESC LIMIT 20",
        (artist_name,),
    ).fetchall()
    st.subheader("Top tracks")
    for t in top_tracks:
        _row(t["name"], dict(page="track_detail", track_name=t["name"], artist_name=artist_name), note=f"×{t['cnt']}")


# ── router ────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Your Spotify Data", page_icon="🎵", layout="wide")

con = get_connection()
qp = st.query_params
page = qp.get("page", "home")

if page == "home":
    page_home(con)
elif page == "search":
    page_search(con, qp.get("query", ""))
elif page == "liked_songs":
    page_liked_songs(con)
elif page == "liked_albums":
    page_liked_albums(con)
elif page == "playlists":
    page_playlists(con)
elif page == "artists":
    page_artists(con)
elif page == "artist_detail":
    page_artist_detail(con, qp.get("artist_name", ""))
elif page == "track_detail":
    page_track_detail(con, qp.get("track_name", ""), qp.get("artist_name", ""))
elif page == "album_detail":
    page_album_detail(con, qp.get("album_name", ""), qp.get("artist_name", ""))
elif page == "playlist_detail":
    page_playlist_detail(con, int(qp.get("playlist_id", 0)), qp.get("playlist_name", ""))

con.close()
