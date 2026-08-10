import pytest

from src.covers.router import _is_allowed_spotify_cdn_host


@pytest.mark.parametrize(
    "hostname, expected",
    [
        ("i.scdn.co", True),
        ("mosaic.scdn.co", True),
        ("cdn.spotifycdn.com", True),
        ("assets.spotifycdn.com", True),
        (None, False),
        ("", False),
        ("evil.com", False),
        ("i.scdn.co.evil.com", False),
        ("notspotifycdn.com", False),
        ("spotifycdn.com", False),
    ],
)
def test_is_allowed_spotify_cdn_host_only_matches_the_real_spotify_cdn(hostname, expected):
    assert _is_allowed_spotify_cdn_host(hostname) is expected
