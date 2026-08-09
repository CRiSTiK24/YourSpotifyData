# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Turns a Spotify GDPR data export into a personal, hostable listening-history site: a FastAPI + htmx backend that reads/writes a SQLite database, with server-rendered HTML (no template engine, no JS framework, no frontend build step).

## Commands

```bash
cd backend
uv run uvicorn src.main:app --reload   # run the app (http://localhost:8000)
uv run ruff check .                    # lint
uv run ruff format .                   # format
```

Config lives in `backend/.env` (see README.md for the full list of vars — `DB_PATH`, `ALLOWED_EMAIL`/`RESEND_API_KEY` for login, `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` for cover art, `SPOTIFY_REDIRECT_URI` for the scrobbler). All are optional; whichever feature needs a missing var just stays unusable rather than failing startup.

There is no test suite currently.

**Deployment**: this instance runs under pm2 as the `spotify` process (port 8501, not the README's default 8000). Code edits do not take effect until it's restarted:

```bash
pm2 restart spotify
pm2 logs spotify --lines 20 --nostream   # sanity-check it came back up clean
```

## Browser verification

`agent-browser` (a CDP-based browser automation CLI) is available for visually checking changes — screenshots, DOM snapshots, clicking through pages. Run `agent-browser skills get core --full` for the full command reference.

Its own managed Chromium launch hangs indefinitely in this sandbox (no visible process/socket, `close --all` hangs too). Instead, launch Chromium manually with remote debugging and point `agent-browser` at it via `--cdp`:

```bash
nohup snap run chromium --headless=new --no-sandbox --disable-gpu \
  --remote-debugging-port=9223 --remote-debugging-address=127.0.0.1 \
  --user-data-dir=/tmp/ab-manual-profile about:blank > /tmp/chrome-manual.log 2>&1 &
disown
sleep 5
curl -s http://127.0.0.1:9223/json/version   # confirm it's up

agent-browser --cdp 9223 open http://localhost:8501/playlists
agent-browser --cdp 9223 set viewport 1400 900
agent-browser --cdp 9223 screenshot /tmp/check.png
```

Every `agent-browser` command in the session needs `--cdp 9223` (or whatever port was used) instead of relying on its default daemon.

## Architecture

**Domain modules** (`backend/src/<domain>/` for albums, artists, auth, covers, library, playlists, scrobbler, search, theme, tracks, upload) follow a consistent split:
- `router.py` — FastAPI routes, returns `HTMLResponse` via `src/html.py` helpers (or JSON/redirects where relevant)
- `service.py` — SQLite queries (raw `sqlite3`, no ORM; `DBDep` from `src/database.py` injects a per-request connection with `row_factory = sqlite3.Row`)
- `views.py` — assembles a route's HTML out of `src/html.py` components (only present where a module has enough view logic to warrant splitting it out of `router.py`)
- `exceptions.py` — module-specific exceptions (only where needed)

**`src/html.py` is the shared component DSL** — every page is Python-generated HTML built from a small set of reusable pieces: `page()` (shell/nav/sidebar), `row()` / `card()` / `grid()` (list vs. tile layouts), `detail_layout()` (track/album/artist/playlist detail pages), `hero_image()`, `copy_list_button()`, etc. New pages should compose these rather than writing raw HTML strings, so visual/behavioral consistency (spacing, hx-boost wiring, escaping) isn't reimplemented per module.

**htmx conventions and gotchas**: the app uses `hx-boost` globally with `hx-target="#content" hx-select="#content"` set on `<body>`. Any element that issues its own `hx-get` for a fragment that doesn't contain `#content` (search dropdowns, infinite-scroll sentinels, lazy-load triggers) **must** explicitly override `hx-target`/`hx-select` on that element — otherwise it inherits body's selectors and the response gets swapped into nothing, silently wiping the page. See the docstrings on `_quick_search_widget`, `infinite_scroll_trigger`, and `lazy_load_trigger` in `src/html.py` for the concrete failure mode; follow the same override pattern for any new fragment-loading element.

**Color palette** is defined once in `src/palette.py` (`Palette` enum) and synced into `frontend/static/style.css`'s generated `:root` block by `sync_css_palette()` on app startup (writes between `/* palette:start */` / `/* palette:end */` markers). Never hand-edit that block — change `Palette` instead.

**Responsive sizing** in `style.css` uses CSS container queries (`container-type: inline-size` on `.panel`, sizes expressed in `cqw` with `clamp()`) rather than viewport-width media queries, since layout width is driven by the panel/column an element sits in (e.g. the two-column detail-page header), not the full viewport. Follow this pattern for new size-dependent CSS rather than introducing `@media` breakpoints.

**Cover art** goes through `/cover` (`src/covers/router.py`), a single choke point that recolors Spotify's source images into the site palette (`src/duotone.py`) and resizes server-side — restricted to Spotify's CDN hosts to avoid SSRF. `raw=true` opts an image out of recoloring (used for playlist covers).

**Background jobs**, started in `main.py`'s lifespan and run as `asyncio` tasks for the life of the process:
- scrobbler poll loop (`src/scrobbler/service.py`) — polls Spotify recently-played every `scrobbler_poll_seconds`
- library sync loop (`src/scrobbler/library_sync.py`) — syncs playlists/liked songs/liked albums/followed artists every `library_sync_poll_seconds`
- image fetch loop (`src/images/service.py`) — throttled cover-art backfill via the Spotify Web API

**Auth** (`src/auth/`) is single-user by design: one allowlisted email (`ALLOWED_EMAIL`), login code delivered via Resend, session cookie. It only gates `/upload` and `/scrobbler`; everything else is public/read-only. `logged_in_var` (a `ContextVar` set by middleware in `main.py`) lets `src/html.py` render the right nav without every route threading auth state through explicitly.

**Data pipeline** (`processors/*.py`) is separate from the FastAPI app — standalone scripts that parse the raw Spotify GDPR export (`data/spotifyRaw/*.json`) into `data/spotifyProcessed/SpotifyData.db` per `data/spotifyProcessed/schema.sql`:
- `StreamingHistoryProcessor.py` — play history
- `YourLibraryProcessor.py` — liked songs/albums, followed artists
- `PlaylistProcessor.py` — playlists (safe to re-run; a playlist missing from a re-upload is deleted along with its tracks)
- `SpotifyImageFetcher.py` — the standalone/manual counterpart to the `images` background loop

Search (`src/search/`) uses a SQLite FTS5 virtual table (`track_history_fts`) kept in sync with `track_history` via triggers defined in `schema.sql`, rather than `LIKE '%word%'` scans — the table has 200k+ rows.
