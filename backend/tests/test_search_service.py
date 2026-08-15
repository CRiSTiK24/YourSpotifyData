from src.search import service as search_service


def _insert_play(db, user_id, name, singer, album=None, time="2024-01-01T10:00:00"):
    db.execute(
        "INSERT INTO track_history (user_id, name, singer, album, time) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, singer, album, time),
    )
    db.commit()


def test_search_track_history_by_name_finds_matches_via_the_fts_index(db, user_id):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, user_id, "Bohemian Rhapsody", "Queen", "A Night at the Opera")

    results = search_service.search_track_history_by_name(db, user_id, "bohemian")
    assert [r["name"] for r in results] == ["Bohemian Rhapsody"]


def test_search_track_history_by_name_does_not_match_the_artist_column(db, user_id):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, user_id, "Some Song", "Cartoon")

    assert search_service.search_track_history_by_name(db, user_id, "cartoon") == []


def test_search_track_history_by_name_reflects_deletions_via_the_fts_sync_trigger(db, user_id):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, user_id, "Deleted Song", "Someone")

    db.execute("DELETE FROM track_history WHERE name = 'Deleted Song'")
    db.commit()

    assert search_service.search_track_history_by_name(db, user_id, "deleted") == []


def test_search_track_history_by_name_never_matches_another_users_plays(db, user_id, other_user_id):
    search_service.ensure_track_history_fts_covers_album(db)
    _insert_play(db, other_user_id, "Their Song", "Someone")

    assert search_service.search_track_history_by_name(db, user_id, "their") == []
