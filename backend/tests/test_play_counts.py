import sqlite3

from src.library import play_counts


def _insert_play(
    con: sqlite3.Connection,
    user_id: int,
    name: str,
    singer: str,
    time: str,
    album: str | None = None,
) -> int:
    cur = con.execute(
        "INSERT INTO track_history (user_id, name, singer, album, time) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, singer, album, time),
    )
    con.commit()
    return cur.lastrowid


def test_ensure_monthly_play_count_tables_backfills_both_all_time_and_monthly_buckets(db, user_id):
    _insert_play(db, user_id, "Song A", "Artist X", "2024-01-15T10:00:00")
    _insert_play(db, user_id, "Song A", "Artist X", "2024-02-15T10:00:00")

    play_counts.ensure_monthly_play_count_tables(db)

    all_time = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song A' AND period = 0"
    ).fetchone()
    jan = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song A' AND period = 202401"
    ).fetchone()
    assert all_time["play_count"] == 2
    assert jan["play_count"] == 1


def test_incremental_insert_after_tables_exist_updates_both_buckets_via_trigger(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song B", "Artist Y", "2024-03-10T10:00:00")

    all_time = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song B' AND period = 0"
    ).fetchone()
    march = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song B' AND period = 202403"
    ).fetchone()
    assert all_time["play_count"] == 1
    assert march["play_count"] == 1


def test_deleting_the_only_play_removes_both_bucket_rows_via_trigger(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    row_id = _insert_play(db, user_id, "Song C", "Artist Z", "2024-04-01T10:00:00")

    db.execute("DELETE FROM track_history WHERE id = ?", (row_id,))
    db.commit()

    remaining = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song C' AND period = 0"
    ).fetchone()
    assert remaining is None


def test_range_query_does_not_double_count_the_all_time_bucket_into_the_month_sum(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song D", "Artist W", "2024-01-01T10:00:00")
    _insert_play(db, user_id, "Song D", "Artist W", "2024-02-01T10:00:00")

    rows = play_counts.load_most_listened(
        db, user_id, limit=10, offset=0, start_period=202401, end_period=202402
    )
    song_d = next(r for r in rows if r["name"] == "Song D")
    assert song_d["play_count"] == 2


def test_load_most_listened_unbounded_reads_the_all_time_bucket(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song E", "Artist V", "2024-01-01T10:00:00")
    _insert_play(db, user_id, "Song E", "Artist V", "2024-06-01T10:00:00")

    rows = play_counts.load_most_listened(db, user_id, limit=10, offset=0)
    song_e = next(r for r in rows if r["name"] == "Song E")
    assert song_e["play_count"] == 2


def test_load_most_listened_single_period_reads_just_that_one_month(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song F", "Artist U", "2024-01-01T10:00:00")
    _insert_play(db, user_id, "Song F", "Artist U", "2024-02-01T10:00:00")

    rows = play_counts.load_most_listened(
        db, user_id, limit=10, offset=0, start_period=202401, end_period=202401
    )
    song_f = next(r for r in rows if r["name"] == "Song F")
    assert song_f["play_count"] == 1


def test_most_listened_period_range_reports_the_actual_min_and_max_months_with_plays(db, user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song G", "Artist T", "2023-05-01T10:00:00")
    _insert_play(db, user_id, "Song G", "Artist T", "2024-11-01T10:00:00")

    lo, hi = play_counts.most_listened_period_range(db, user_id)
    assert lo == 202305
    assert hi == 202411


def test_load_most_listened_never_returns_another_users_plays(db, user_id, other_user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "My Song", "Artist X", "2024-01-01T10:00:00")
    _insert_play(db, other_user_id, "Their Song", "Artist Y", "2024-01-01T10:00:00")

    rows = play_counts.load_most_listened(db, user_id, limit=10, offset=0)
    assert [r["name"] for r in rows] == ["My Song"]


def test_load_most_listened_with_no_user_id_sums_plays_across_every_user(
    db, user_id, other_user_id
):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Shared Song", "Artist X", "2024-01-01T10:00:00")
    _insert_play(db, user_id, "Shared Song", "Artist X", "2024-01-02T10:00:00")
    _insert_play(db, other_user_id, "Shared Song", "Artist X", "2024-01-03T10:00:00")

    rows = play_counts.load_most_listened(db, None, limit=10, offset=0)
    shared = next(r for r in rows if r["name"] == "Shared Song")
    assert shared["play_count"] == 3


def test_load_most_listened_with_no_user_id_sums_a_specific_period_too(db, user_id, other_user_id):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Shared Song", "Artist X", "2024-01-01T10:00:00")
    _insert_play(db, other_user_id, "Shared Song", "Artist X", "2024-01-02T10:00:00")
    _insert_play(db, other_user_id, "Shared Song", "Artist X", "2024-02-01T10:00:00")

    rows = play_counts.load_most_listened(
        db, None, limit=10, offset=0, start_period=202401, end_period=202401
    )
    shared = next(r for r in rows if r["name"] == "Shared Song")
    assert shared["play_count"] == 2


def test_most_listened_stats_with_no_user_id_counts_distinct_tracks_across_users(
    db, user_id, other_user_id
):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, user_id, "Song A", "Artist X", "2024-01-01T10:00:00")
    _insert_play(db, other_user_id, "Song A", "Artist X", "2024-01-02T10:00:00")
    _insert_play(db, other_user_id, "Song B", "Artist Y", "2024-01-01T10:00:00")

    count, max_plays = play_counts.most_listened_stats(db, None)
    assert count == 2
    assert max_plays == 2
