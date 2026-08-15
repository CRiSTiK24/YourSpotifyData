-- One owner (fixed at first startup, from OWNER_USERNAME/ALLOWED_EMAIL) plus
-- up to 4 member accounts the owner adds from /admin. Every other table
-- below is scoped to a user_id from this table (except album_images and
-- artist_images, a shared name-keyed cover-art cache - see CLAUDE.md).
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    email           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL CHECK (role IN ('owner','member')),
    created_at      TEXT NOT NULL,
    playlist_rules  TEXT
);

CREATE TABLE IF NOT EXISTS playlists (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    name                  TEXT NOT NULL,
    spotify_playlist_id   TEXT,
    spotify_snapshot_id   TEXT,
    image_url             TEXT,
    description           TEXT,
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id);

CREATE TABLE IF NOT EXISTS track_history (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id),
    name               TEXT NOT NULL,
    singer             TEXT,
    album              TEXT,
    time               TEXT NOT NULL,
    spotify_track_uri  TEXT
);

CREATE INDEX IF NOT EXISTS idx_track_history_user_id ON track_history(user_id);

-- Speeds up equality lookups/joins against this table by (name, singer) —
-- e.g. search's LEFT JOIN from library_tracks/playlist_tracks, and
-- get_album_image's representative-track lookup. Doesn't help the FTS
-- MATCH queries above (those use track_history_fts instead), only exact
-- and prefix equality via this index.
CREATE INDEX IF NOT EXISTS idx_track_history_name_singer ON track_history(name, singer);

-- Full-text index over track_history(name, singer, album) — LIKE '%word%'
-- on this table (206k+ rows and growing) forces a full scan on every
-- search keystroke; FTS5 turns that into a token lookup, used by the
-- quick-search Tracks/Artists/Albums tabs (each restricted to its own
-- column via FTS5's `col: term` syntax - see fts_match_query() in
-- src/utils.py). content='track_history' means this table stores no data
-- of its own, just the index — it mirrors rowids from track_history, kept
-- in sync by the triggers below. (If you're looking at an existing
-- database that predates the `album` column here, src/search/service.py's
-- ensure_fts_migrations() rebuilds it automatically on startup - this
-- definition only matters for a fresh install.) No user_id here by design -
-- every FTS-based query re-joins to track_history by rowid and filters
-- th.user_id there instead, so the index itself stays a pure text index.
CREATE VIRTUAL TABLE IF NOT EXISTS track_history_fts USING fts5(
    name, singer, album, content='track_history', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS track_history_ai AFTER INSERT ON track_history BEGIN
    INSERT INTO track_history_fts(rowid, name, singer, album)
    VALUES (new.id, new.name, new.singer, new.album);
END;

CREATE TRIGGER IF NOT EXISTS track_history_ad AFTER DELETE ON track_history BEGIN
    INSERT INTO track_history_fts(track_history_fts, rowid, name, singer, album)
    VALUES ('delete', old.id, old.name, old.singer, old.album);
END;

CREATE TRIGGER IF NOT EXISTS track_history_au AFTER UPDATE ON track_history BEGIN
    INSERT INTO track_history_fts(track_history_fts, rowid, name, singer, album)
    VALUES ('delete', old.id, old.name, old.singer, old.album);
    INSERT INTO track_history_fts(rowid, name, singer, album)
    VALUES (new.id, new.name, new.singer, new.album);
END;

CREATE TABLE IF NOT EXISTS library_tracks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id),
    track_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_track_uri  TEXT,
    UNIQUE(user_id, track_name, artist_name)
);

CREATE INDEX IF NOT EXISTS idx_library_tracks_user_id ON library_tracks(user_id);

CREATE TABLE IF NOT EXISTS library_albums (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id),
    album_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_album_uri  TEXT,
    UNIQUE(user_id, album_name, artist_name)
);

CREATE INDEX IF NOT EXISTS idx_library_albums_user_id ON library_albums(user_id);

CREATE TABLE IF NOT EXISTS library_artists (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    artist_name         TEXT NOT NULL,
    spotify_artist_uri  TEXT,
    UNIQUE(user_id, artist_name)
);

CREATE INDEX IF NOT EXISTS idx_library_artists_user_id ON library_artists(user_id);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id),
    playlist_id        INTEGER NOT NULL REFERENCES playlists(id),
    track_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_track_uri  TEXT,
    UNIQUE(playlist_id, track_name, artist_name)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_user_id ON playlist_tracks(user_id);

-- Populated by processors/SpotifyImageFetcher.py, keyed by name to match
-- how the rest of the schema joins/displays data. A row with image_url
-- IS NULL but fetched_at set means "looked up, no match" so reruns don't
-- retry known dead ends. Deliberately global/not user-scoped - it's a
-- lookup cache keyed by real-world artist/album names, so two users with
-- the same artist in their history share one fetch instead of duplicating
-- the external API call and the stored row.
CREATE TABLE IF NOT EXISTS album_images (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name       TEXT NOT NULL,
    album_name        TEXT NOT NULL,
    spotify_album_id  TEXT,
    image_url         TEXT,
    fetched_at        TEXT NOT NULL,
    UNIQUE(artist_name, album_name)
);

CREATE TABLE IF NOT EXISTS artist_images (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name        TEXT NOT NULL UNIQUE,
    spotify_artist_id  TEXT,
    image_url          TEXT,
    genres             TEXT,
    fetched_at         TEXT NOT NULL
);

-- Web login sessions (email-code auth), tied to the user who logged in.
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

-- One row per connected Spotify account (up to 5, one per user) - OAuth
-- tokens for the background scrobbler poller, plus a running status so
-- /scrobbler can show it.
CREATE TABLE IF NOT EXISTS scrobbler_tokens (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id),
    access_token   TEXT NOT NULL,
    refresh_token  TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    connected_at   TEXT NOT NULL,
    last_poll_at   TEXT,
    last_poll_new  INTEGER,
    last_error     TEXT
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL REFERENCES users(id),
    status               TEXT NOT NULL, -- queued | extracting | processing | done | error
    message              TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    new_history_rows     INTEGER,
    new_library_tracks   INTEGER,
    new_library_albums   INTEGER,
    new_library_artists  INTEGER,
    new_playlists        INTEGER,
    new_playlist_tracks  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_user_id ON import_jobs(user_id);
