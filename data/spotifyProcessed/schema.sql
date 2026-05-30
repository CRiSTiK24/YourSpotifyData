CREATE TABLE IF NOT EXISTS playlists (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS track_history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    singer  TEXT,
    time    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name  TEXT NOT NULL,
    artist_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_albums (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    album_name  TEXT NOT NULL,
    artist_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL REFERENCES playlists(id),
    track_name  TEXT NOT NULL,
    artist_name TEXT NOT NULL
);
