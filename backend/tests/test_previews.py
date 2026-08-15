from src.previews.service import _extract_preview_url, resolve_track_id


def test_extract_preview_url_finds_url_in_embed_page_json():
    html = (
        '<script>{"props":{"audioPreview":{"url":"https://p.scdn.co/mp3-preview/abc123",'
        '"format":"MP3_96"}}}</script>'
    )
    assert _extract_preview_url(html) == "https://p.scdn.co/mp3-preview/abc123"


def test_extract_preview_url_returns_none_when_absent():
    html = '<script>{"props":{"someOtherField":true}}</script>'
    assert _extract_preview_url(html) is None


def test_resolve_track_id_extracts_id_from_track_history_uri(db, user_id):
    db.execute(
        "INSERT INTO track_history (user_id, name, singer, time, spotify_track_uri) "
        "VALUES (?, 'Song', 'Artist', '2024-01-01T00:00:00Z', 'spotify:track:abc123')",
        (user_id,),
    )
    db.commit()
    assert resolve_track_id(db, "Song", "Artist") == "abc123"


def test_resolve_track_id_returns_none_when_not_found(db):
    assert resolve_track_id(db, "Missing", "Nobody") is None
