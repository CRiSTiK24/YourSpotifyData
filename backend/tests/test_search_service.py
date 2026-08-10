from src.search import service as search_service


def _insert_play(db, name, singer, album=None, time="2024-01-01T10:00:00"):
    db.execute(
        "INSERT INTO track_history (name, singer, album, time) VALUES (?, ?, ?, ?)",
        (name, singer, album, time),
    )
    db.commit()


def test_search_track_history_by_name_finds_matches_via_the_fts_index(db):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, "Bohemian Rhapsody", "Queen", "A Night at the Opera")

    results = search_service.search_track_history_by_name(db, "bohemian")
    assert [r["name"] for r in results] == ["Bohemian Rhapsody"]


def test_search_track_history_by_name_does_not_match_the_artist_column(db):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, "Some Song", "Cartoon")

    assert search_service.search_track_history_by_name(db, "cartoon") == []


def test_search_track_history_by_name_reflects_deletions_via_the_fts_sync_trigger(db):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, "Deleted Song", "Someone")

    db.execute("DELETE FROM track_history WHERE name = 'Deleted Song'")
    db.commit()

    assert search_service.search_track_history_by_name(db, "deleted") == []
