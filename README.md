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

## Prerequisites

- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — installs and manages the Python version and dependencies for you, nothing else to set up:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  Verify with `uv --version`.
- **Node.js** — only needed if you're using pm2 to host it persistently (step 2 below); skip this if you're just trying it out locally. Install via your OS package manager or [nodejs.org](https://nodejs.org/); verify with `node --version`.

## Getting started

**1. Request your Spotify data**

Go to [Spotify Privacy Settings](https://support.spotify.com/us/article/data-rights-and-privacy-settings/), request your extended streaming history, and wait for the download link (can take up to 30 days, in my case it took 4).

**2. Run the app**

No database setup needed — a fresh clone bootstraps its own empty SQLite database (schema included) the first time it starts.

For trying it out locally:

```bash
cd backend
uv run uvicorn src.main:app --reload
```

Open `http://localhost:8000` in your browser.

To actually host it (keeps running after you close the terminal, restarts itself if it crashes), use [pm2](https://pm2.keymetrics.io/) instead. Install Node.js, then:

```bash
npm install -g pm2
pm2 start ecosystem.config.js   # from the repo root - edit the port inside first if 8000 is taken
pm2 save                        # remember it across reboots
pm2 startup                     # prints a command to run once, so pm2 itself starts on boot
```

Useful afterward: `pm2 logs your-spotify-data` (see what it's doing, and the `/setup` token below), `pm2 restart your-spotify-data` (after pulling an update).

By default the database lives at `data/spotifyProcessed/SpotifyData.db`; set `DB_PATH` in `backend/.env` to point it elsewhere.

**3. First-run setup**

The first visit redirects to `/setup` (every other page does too, until this is done). It'll ask for a **setup token** — a one-time code printed to the server's logs (`pm2 logs your-spotify-data`, or the terminal if running directly) the first time it starts with no owner yet, and also saved to `backend/.setup_token`. This proves whoever completes setup actually has access to the server, not just a browser.

Fill in your email and a username — that becomes the **owner** account, the one with admin access — then log in with the email you gave. You can also optionally fill in a [Resend](https://resend.com) API key (for email login codes) and Spotify app credentials (for cover art / the scrobbler, see below) here or later; nothing needs a restart to take effect, and you can revisit `/setup` any time afterward (as the owner) to change them.

Once logged in, up to 4 more accounts can be added from the Account page (owner-only) — each gets fully isolated history, playlists, and their own scrobbler connection under `/their-username/...`.

**4. Upload your export**

Data gets in through the browser, not by hand-placing files. From the Account page, drop your Spotify zip under Upload. Re-uploading a newer export later only adds what's new.

**5. Fetch cover art**

Needs `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` (Development Mode, Client Credentials flow, no user login needed) from the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) — set via `/setup` or `backend/.env`. It's an automated background job, but sadly it's heavily throttled by Spotify.

**6. Enable the scrobbler**

Rather than re-uploading exports, link your Spotify account once and let the app poll for new plays automatically. In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard): allowlist yourself under "Users and Access" (Development Mode requires it) and add a Redirect URI — **it must include your username**, e.g. `https://your-domain/your-username/scrobbler/callback` (not just `/scrobbler/callback`), matching whatever `SPOTIFY_REDIRECT_URI` you set. Then from the Account page hit "Connect Spotify". From then on it checks recently-played every 15 minutes and adds anything new.
