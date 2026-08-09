from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.html import page

router = APIRouter(tags=["home"])

ABOUT_HTML = """
<p class="subtitle">At the moment this is a one-person thing which has already been done in
other projects. But what I'd like is that anyone can drop their Spotify export into a
browser, have it processed on the backend, and land in a real database alongside
everyone else's.</p>
<p class="subtitle">From one side there are many times where I've felt that it's very hard
to actually play with your own data, even this workaround to avoid using the API (because
it's been restricted to any new project) will take a few days of receiving the files, and
if you'd like to keep it synchronised you'd need to do something like LastFM who have
access to new streams. Also on the other side, I feel frustrated when I'm digging through
Spotify and there is no easy way to find other playlists that have X amount of songs in
common with me.</p>
<p class="subtitle">I saw some other projects doing some kind of fuzzy search based on the
title of the playlists or others, but tbh I think that we should be able to use that data
outside the platform, and do our own comparisons, recommendations and searches if the app
is not on par with our desires. Thus is what I hope to do with this repo, making a way to
not only see your own data, but to be able to also add your friend's or other music
enthusiasts' data and to be able to delve deep into whatever picks your curiosity, after
all music is such a beloved hobby for a reason.</p>
"""


@router.get(
    "/", response_class=HTMLResponse, status_code=200, description="Home page"
)
def home():
    return page(ABOUT_HTML)
