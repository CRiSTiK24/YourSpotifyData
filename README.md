# YourSpotifyData

> Turn your Spotify GDPR data export into a personal, interactive listening history you can host publicly

Spotify lets you [request a full copy of your data](https://support.spotify.com/us/article/data-rights-and-privacy-settings/) under GDPR. The export contains your complete streaming history, liked songs, liked albums, and playlists but it's raw JSON files in ZIPs.

This project processes that data into a local SQLite database and exposes it through a FastAPI + htmx web app, so you can browse, search, and visualise everything in one place. You can see it with my own data in [https://cristik.duckdns.org](https://cristik.duckdns.org)



## What you can do

- **Search** any song, artist, or album with fuzzy multi-word matching
- **Browse** your liked songs, liked albums, playlists, and artists
- **Visualise** listening history with an interactive double heatmap (year → month → day drill-down)
- **Navigate** between tracks, albums, artists, and playlists

## Why this project?

At the moment this is a one-person thing which has already been done in other projects. But what I'd like is that anyone can drop their Spotify export into a browser, have it processed on the backend, and land in a real database alongside everyone else's.

 From one side there are many times where I've felt that it's very hard to actually play with your own data, even this workaround to avoid using the API (because it's been restricted to any new project) will take a few days of receiving the files, and if you'd like to keep it synchronised you'd need to do something like LastFM who have access to new streams. Also on the other side, I feel frustrated when I'm digging through Spotify and there is no easy way to find other playlists that have X amount of songs in common with me. 
 
 I saw some other projects doing some kind of fuzzy search based on the title of the playlists or others, but tbh I think that we should be able to use that data outside the platform, and do our own comparisons, recommendations and searches if the app is not on par with our desires. Thus is what I hope to do with this repo, making a way to not only see your own data, but to be able to also add your friend's or other music enthusiasts' data and to be able to delve deep into whatever picks your curiosity, after all music is such a beloved hobby for a reason.

## Getting started

**1. Request your Spotify data**

Go to [Spotify Privacy Settings](https://support.spotify.com/us/article/data-rights-and-privacy-settings/), request your extended streaming history, and wait for the download link (can take up to 30 days, in my case it took 4). You'll need the Account data for the Playlists and Liked Songs/Albums information, and the Spotify Extended Streaming History for the whole of it. Be aware that they are not 100% synchronised, so new tracks in the Account Data might not be in the Extended Streaming History yet.

**2. Place your raw data**

Extract the Spotify zip and put the relevant files into `data/spotifyRaw/`:

| File | Description |
|------|-------------|
| `Streaming_History_Audio_*.json` | Full play history |
| `YourLibrary.json` | Liked songs and albums |
| `Playlist*.json` | Your playlists |

**3. Process the data**

These only use the standard library, so no `uv`/venv is needed:

```bash
python3 processors/StreamingHistoryProcessor.py
python3 processors/YourLibraryProcessor.py
python3 processors/PlaylistProcessor.py
```

**4. Run the app**

```bash
cd backend
uv run uvicorn src.main:app --reload
```

Open `http://localhost:8000` in your browser. You should be able to see the same as in https://cristik.duckdns.org/ but with your own data loaded.

By default the app reads the database from `data/spotifyProcessed/SpotifyData.db`. To point it elsewhere, set `DB_PATH` in `backend/.env`.
