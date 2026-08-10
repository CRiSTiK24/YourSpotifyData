import pytest

from src.heatmap import _cell_color, build_heatmap_data, period_label, resolve_period_filter


@pytest.mark.parametrize(
    "result, expected",
    [
        ((2024, None, None, []), "2024"),
        ((2024, 8, None, []), "Aug 2024"),
        ((2024, 8, 15, []), "Aug 15, 2024"),
    ],
)
def test_period_label_shows_the_narrowest_selected_granularity(result, expected):
    assert period_label(result) == expected


def test_resolve_period_filter_passes_full_history_through_unfiltered_when_no_selection():
    history = [{"name": "A"}, {"name": "B"}]
    plays, count, filter_clear_html = resolve_period_filter(history, None, "/artist/X")
    assert plays == history
    assert count == 2
    assert filter_clear_html == ""


def test_resolve_period_filter_narrows_to_just_the_selected_periods_plays():
    history = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    result = (2024, 8, None, [{"name": "A"}])
    plays, count, filter_clear_html = resolve_period_filter(history, result, "/artist/X")
    assert plays == [{"name": "A"}]
    assert count == 1
    assert filter_clear_html != ""


def test_cell_color_zero_plays_is_its_own_distinct_tier():
    assert _cell_color(0) != _cell_color(1)


def test_cell_color_includes_the_threshold_value_itself_in_the_lower_tier():
    assert _cell_color(50) == _cell_color(1)
    assert _cell_color(100) == _cell_color(51)
    assert _cell_color(200) == _cell_color(101)


def test_cell_color_crosses_into_the_next_tier_just_past_each_threshold():
    assert _cell_color(51) != _cell_color(50)
    assert _cell_color(101) != _cell_color(100)
    assert _cell_color(201) != _cell_color(200)


def test_build_heatmap_data_buckets_plays_by_year_and_month_from_the_timestamp_string():
    history = [
        {"time": "2024-01-05T10:00:00"},
        {"time": "2024-01-20T10:00:00"},
        {"time": "2024-02-01T10:00:00"},
    ]
    counts, by_month, years = build_heatmap_data(history)
    assert counts == {(2024, 1): 2, (2024, 2): 1}
    assert years == [2024]
    assert len(by_month[(2024, 1)]) == 2


def test_build_heatmap_data_extracts_the_day_of_month_from_the_timestamp():
    history = [{"time": "2024-01-05T10:00:00"}]
    _counts, by_month, _years = build_heatmap_data(history)
    assert by_month[(2024, 1)][0]["day"] == 5


def test_build_heatmap_data_only_includes_track_name_singer_album_when_present_on_the_row():
    history_without_track_info = [{"time": "2024-01-05T10:00:00"}]
    _counts, by_month, _years = build_heatmap_data(history_without_track_info)
    assert by_month[(2024, 1)][0] == {"day": 5}

    history_with_track_info = [
        {"time": "2024-01-05T10:00:00", "name": "Song", "singer": "Artist", "album": "Album"}
    ]
    _counts, by_month, _years = build_heatmap_data(history_with_track_info)
    entry = by_month[(2024, 1)][0]
    assert entry["name"] == "Song"
    assert entry["singer"] == "Artist"
    assert entry["album"] == "Album"
