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
uv run pytest                          # run tests
```

Config lives in `backend/.env` (see README.md for the full list of vars — `DB_PATH`, `ALLOWED_EMAIL`/`RESEND_API_KEY` for login, `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` for cover art, `SPOTIFY_REDIRECT_URI` for the scrobbler). All are optional; whichever feature needs a missing var just stays unusable rather than failing startup.

Dependencies are pinned in `backend/pyproject.toml` (`uv sync` to install) — don't fall back to an ambient/shared venv, this project needs its own.

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

**htmx conventions and gotchas**: the app uses `hx-boost` globally with `hx-target="#content" hx-select="#content"` set on `<body>`. Any element that issues its own `hx-get` for a fragment that doesn't contain `#content` (search dropdowns, infinite-scroll sentinels, lazy-load triggers) **must** explicitly override `hx-target`/`hx-select` on that element (`hx-target='this' hx-select='unset'` is the pattern used throughout `src/html.py`) — otherwise it inherits body's selectors, and since the fragment response has no `#content` element, that inherited select-and-swap wipes the entire page content out instead of updating just the element. Follow this same override pattern for any new fragment-loading element (see `paginated_fragment`/`infinite_scroll_trigger`/`lazy_load_trigger`/`_quick_search_widget` in `src/html.py` for the current call sites — the code itself has no comments explaining this anymore, this paragraph is the documentation).

**Code has (almost) no comments by design.** Context that would otherwise live in a docstring or inline comment belongs in a descriptive name instead wherever possible (e.g. `_is_allowed_spotify_cdn_host`, `MAX_ZIP_SIZE_COMPRESSED`, `run_periodic`'s `require_connected` param). Where a name genuinely can't carry the reasoning, the comment was stripped anyway and, if the gotcha was load-bearing, folded into this file instead — so treat CLAUDE.md, not the source, as the place to look for and add "why" context. A few gotchas worth knowing that aren't obvious from names alone:
- `src/database.py`'s `get_connection()` uses `check_same_thread=False` because the async `/upload` route resolves its `DBDep` in a different worker thread than the request handler body runs in; every other route is still one fresh connection per request, closed at the end, so there's no real concurrent-use risk.
- `src/scrobbler/loop.py` exists as its own module, separate from `service.py`, specifically to avoid a circular import (`service.py` needs `run_periodic`; `run_periodic` takes a `require_connected` callback rather than importing `service.get_status` directly, which would import back into `service.py`) — don't "clean this up" by merging it back into `service.py`.
- `src/html.py`'s `page()` includes a `<script>` reading `localStorage` theme overrides inline in `<head>`, before the stylesheet/htmx load — intentional, to avoid a flash of unstyled/default theme on load, not dead code to remove.

**Color palette** is defined once in `src/palette.py` (`Palette` enum) and synced into `frontend/static/style.css`'s generated `:root` block by `sync_css_palette()` on app startup (writes between `/* palette:start */` / `/* palette:end */` markers). Never hand-edit that block — change `Palette` instead.

**Responsive sizing** in `style.css` uses CSS container queries (`container-type: inline-size` on `.panel`, sizes expressed in `cqw` with `clamp()`) rather than viewport-width media queries, since layout width is driven by the panel/column an element sits in (e.g. the two-column detail-page header), not the full viewport. Follow this pattern for new size-dependent CSS rather than introducing `@media` breakpoints.

**Cover art** goes through `/cover` (`src/covers/router.py`), a single choke point that recolors Spotify's source images into the site palette (`src/duotone.py`) and resizes server-side — restricted to Spotify's CDN hosts to avoid SSRF. `raw=true` opts an image out of recoloring (used for playlist covers).

**Background jobs**, started in `main.py`'s lifespan and run as `asyncio` tasks for the life of the process:
- scrobbler poll loop (`src/scrobbler/service.py`) — polls Spotify recently-played every `scrobbler_poll_seconds`
- library sync loop (`src/scrobbler/library_sync.py`) — syncs playlists/liked songs/liked albums/followed artists every `library_sync_poll_seconds`
- image fetch loop (`src/images/service.py`) — throttled cover-art backfill via the Spotify Web API

**Multiuser**: one **owner** account plus up to 4 **member** accounts (`src/users/`, `MAX_USERS = 5`), each with fully isolated data — every user-scoped table carries a `user_id` column (except `album_images`/`artist_images`, a deliberately shared name-keyed cover-art cache — two users' identical artist/album still share one fetch). Every content route lives under `/{username}/...`; `main.py`'s `user_router` resolves that segment via `users_service.resolve_viewed_user` (404 if unknown) and injects the target row as `ViewedUserDep`. `src/html.py`'s `u(path)` helper prepends the *current* username (a `ContextVar` set by middleware) to any in-app link/redirect — always use it instead of a bare `f"/{path}"` for anything under the user prefix.

**Auth** (`src/auth/`): login code by email via Resend, session cookie tied to a `user_id`. `require_write_access` (current user must be the owner, or exactly the `{username}` being viewed) gates Upload/Scrobbler/Profile — all unified onto one `/{username}/account` hub page (`src/account/router.py` composes each module's own content-builder function into one page; those routes' bare `GET`s now just redirect there). `require_admin` (owner, and only from their own page) additionally gates the Admin section. `can_write_var`/`is_owner_home_var` (`ContextVar`s set by the same middleware) drive sidebar visibility without threading auth state through every route.

**First run**: if no owner account exists yet, `main.py`'s middleware redirects every request to `/setup` (`src/setup/`) except `/static/*`. Completing setup requires a one-time **setup token** (Jenkins-style: generated on boot, printed to logs, persisted to `backend/.setup_token`, consumed on use) so claiming the instance needs filesystem/log access, not just being the first HTTP visitor. That page creates the owner and can set `RESEND_API_KEY`/`SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`/`SPOTIFY_REDIRECT_URI`, all written via `src/app_settings.py` into a DB-backed `app_settings` table rather than `backend/.env` — `app_settings.get(con)` returns the DB value if set, else falls back to `src.config.settings`'s env-var equivalent, so existing `.env`-configured instances keep working unmigrated. Nothing here needs a restart: `create_owner` + `ensure_schema` + the settings write all run synchronously, and every consumer (auth's Resend send, the scrobbler, the image-fetch loop) re-reads `app_settings.get(con)` per use rather than caching it at startup. The owner can revisit `/setup` any time afterward to change these values (gated by `require_admin`-equivalent role check in `setup/router.py`).

**Data pipeline** (`processors/*.py`) is separate from the FastAPI app — standalone scripts that parse the raw Spotify GDPR export (`data/spotifyRaw/*.json`) into `data/spotifyProcessed/SpotifyData.db` per `data/spotifyProcessed/schema.sql`:
- `StreamingHistoryProcessor.py` — play history
- `YourLibraryProcessor.py` — liked songs/albums, followed artists
- `PlaylistProcessor.py` — playlists (safe to re-run; a playlist missing from a re-upload is deleted along with its tracks)
- `SpotifyImageFetcher.py` — the standalone/manual counterpart to the `images` background loop

`src/upload/service.py`'s web `/upload` flow deliberately only runs `StreamingHistoryProcessor.py` (`UPLOAD_PROCESSOR_SCRIPTS`) — liked songs/albums/followed artists and playlists come from the scrobbler's live library sync (`src/scrobbler/library_sync.py`) instead, not from re-uploading the export.

Search (`src/search/`) uses a SQLite FTS5 virtual table (`track_history_fts`) kept in sync with `track_history` via triggers defined in `schema.sql`, rather than `LIKE '%word%'` scans — the table has 200k+ rows.

**Testing** (`backend/tests/`, run via `uv run pytest`) follows a strict gate before any test gets written, adapted from PostHog's own internal testing philosophy: before writing a test, name the specific regression it would catch — a concrete bug, code path, and input that would break. If you can't name it, don't write the test; coverage-chasing and change-detector tests (asserting internal call order/private-method mocking) are explicitly not wanted here. Cheapest-first: prefer a pure-function unit test (no DB/network) over a DB-backed test over a full endpoint test — extract logic into a pure function first if that's what it takes to test it cheaply. When a test does need I/O, mock only true external boundaries (network calls, the Spotify/Resend APIs) — never internal helpers or private methods. `tests/conftest.py`'s `db` fixture gives a fresh in-memory SQLite DB built from the real `data/spotifyProcessed/schema.sql` per test, so DB-backed tests (e.g. `test_play_counts.py`, which exercises the `track_play_counts`/`album_play_counts`/`artist_play_counts` trigger-maintained bookkeeping — the most correctness-critical logic in the app) run against real schema and triggers, not a mock.
