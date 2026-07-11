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

Go to [Spotify Privacy Settings](https://support.spotify.com/us/article/data-rights-and-privacy-settings/), request your extended streaming history, and wait for the download link (can take up to 30 days, in my case it took 4).

**2. Run the app**

```bash
cd backend
uv run uvicorn src.main:app --reload
```

Open `http://localhost:8000` in your browser. By default it reads the database from `data/spotifyProcessed/SpotifyData.db`; set `DB_PATH` in `backend/.env` to point it elsewhere.

**3. Enable login and upload your export**

Data gets in through the browser, not by hand-placing files. Login is gated by email code (there's exactly one authorized account: mine :O), sent via [Resend](https://resend.com). Sign up, grab an API key, and in `backend/.env` set:

```
ALLOWED_EMAIL=you@example.com
RESEND_API_KEY=re_xxxxxxxx
RESEND_FROM=onboarding@resend.dev
```

Log in, then drop your Spotify zip at `/upload`. Re-uploading a newer export later only adds what's new.

**4. Fetch cover art**

Register an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) (Development Mode, Client Credentials flow, no user login needed) and set `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` in `backend/.env`. It's an automated background job, but sadly it's heavily throttled by Spotify.

**5. Enable the scrobbler**

Rather than re-uploading exports, link your Spotify account once and let the app poll for new plays automatically. In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard): allowlist yourself under "Users and Access" (Development Mode requires it) and add a Redirect URI, e.g. `https://your-domain/scrobbler/callback`. Then set it in `backend/.env`:

```
SPOTIFY_REDIRECT_URI=https://your-domain/scrobbler/callback
```

Visit `/scrobbler` (same login as `/upload`) and hit "Connect Spotify". From then on it checks recently-played every 15 minutes and adds anything new.
