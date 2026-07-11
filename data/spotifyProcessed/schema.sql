CREATE TABLE IF NOT EXISTS playlists (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS track_history (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    singer             TEXT,
    album              TEXT,
    time               TEXT NOT NULL,
    spotify_track_uri  TEXT
);

CREATE TABLE IF NOT EXISTS library_tracks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_track_uri  TEXT,
    UNIQUE(track_name, artist_name)
);

CREATE TABLE IF NOT EXISTS library_albums (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    album_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_album_uri  TEXT,
    UNIQUE(album_name, artist_name)
);

CREATE TABLE IF NOT EXISTS library_artists (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name         TEXT NOT NULL UNIQUE,
    spotify_artist_uri  TEXT
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id        INTEGER NOT NULL REFERENCES playlists(id),
    track_name         TEXT NOT NULL,
    artist_name        TEXT NOT NULL,
    spotify_track_uri  TEXT,
    UNIQUE(playlist_id, track_name, artist_name)
);

-- Populated by processors/SpotifyImageFetcher.py, keyed by name to match
-- how the rest of the schema joins/displays data. A row with image_url
-- IS NULL but fetched_at set means "looked up, no match" so reruns don't
-- retry known dead ends.
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
    fetched_at         TEXT NOT NULL
);

-- Web login sessions (email-code auth gates the upload flow only).
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

-- Single-row table (id always 1): OAuth tokens for the background
-- scrobbler poller, plus a running status so /scrobbler can show it.
CREATE TABLE IF NOT EXISTS scrobbler_tokens (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
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
