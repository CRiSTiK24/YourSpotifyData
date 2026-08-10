import sqlite3

from src.library import play_counts


def _insert_play(
    con: sqlite3.Connection, name: str, singer: str, time: str, album: str | None = None
) -> int:
    cur = con.execute(
        "INSERT INTO track_history (name, singer, album, time) VALUES (?, ?, ?, ?)",
        (name, singer, album, time),
    )
    con.commit()
    return cur.lastrowid


def test_ensure_monthly_play_count_tables_backfills_both_all_time_and_monthly_buckets(db):
    _insert_play(db, "Song A", "Artist X", "2024-01-15T10:00:00")
    _insert_play(db, "Song A", "Artist X", "2024-02-15T10:00:00")

    play_counts.ensure_monthly_play_count_tables(db)

    all_time = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song A' AND period = 0"
    ).fetchone()
    jan = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song A' AND period = 202401"
    ).fetchone()
    assert all_time["play_count"] == 2
    assert jan["play_count"] == 1


def test_incremental_insert_after_tables_exist_updates_both_buckets_via_trigger(db):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, "Song B", "Artist Y", "2024-03-10T10:00:00")

    all_time = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song B' AND period = 0"
    ).fetchone()
    march = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song B' AND period = 202403"
    ).fetchone()
    assert all_time["play_count"] == 1
    assert march["play_count"] == 1


def test_deleting_the_only_play_removes_both_bucket_rows_via_trigger(db):
    play_counts.ensure_monthly_play_count_tables(db)
    row_id = _insert_play(db, "Song C", "Artist Z", "2024-04-01T10:00:00")

    db.execute("DELETE FROM track_history WHERE id = ?", (row_id,))
    db.commit()

    remaining = db.execute(
        "SELECT play_count FROM track_play_counts WHERE name = 'Song C' AND period = 0"
    ).fetchone()
    assert remaining is None


def test_range_query_does_not_double_count_the_all_time_bucket_into_the_month_sum(db):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, "Song D", "Artist W", "2024-01-01T10:00:00")
    _insert_play(db, "Song D", "Artist W", "2024-02-01T10:00:00")

    rows = play_counts.load_most_listened(
        db, limit=10, offset=0, start_period=202401, end_period=202402
    )
    song_d = next(r for r in rows if r["name"] == "Song D")
    assert song_d["play_count"] == 2


def test_load_most_listened_unbounded_reads_the_all_time_bucket(db):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, "Song E", "Artist V", "2024-01-01T10:00:00")
    _insert_play(db, "Song E", "Artist V", "2024-06-01T10:00:00")

    rows = play_counts.load_most_listened(db, limit=10, offset=0)
    song_e = next(r for r in rows if r["name"] == "Song E")
    assert song_e["play_count"] == 2


def test_load_most_listened_single_period_reads_just_that_one_month(db):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, "Song F", "Artist U", "2024-01-01T10:00:00")
    _insert_play(db, "Song F", "Artist U", "2024-02-01T10:00:00")

    rows = play_counts.load_most_listened(
        db, limit=10, offset=0, start_period=202401, end_period=202401
    )
    song_f = next(r for r in rows if r["name"] == "Song F")
    assert song_f["play_count"] == 1


def test_most_listened_period_range_reports_the_actual_min_and_max_months_with_plays(db):
    play_counts.ensure_monthly_play_count_tables(db)
    _insert_play(db, "Song G", "Artist T", "2023-05-01T10:00:00")
    _insert_play(db, "Song G", "Artist T", "2024-11-01T10:00:00")

    lo, hi = play_counts.most_listened_period_range(db)
    assert lo == 202305
    assert hi == 202411
