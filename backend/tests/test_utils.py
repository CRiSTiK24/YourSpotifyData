import pytest

from src.utils import (
    aggregate_plays,
    format_month_param,
    fts_match_query,
    most_listened_next_href,
    parse_month_param,
    pluralize,
)


@pytest.mark.parametrize(
    "n, word, expected",
    [
        (0, "play", "0 plays"),
        (1, "play", "1 play"),
        (2, "play", "2 plays"),
        (1, "time", "1 time"),
        (5, "time", "5 times"),
    ],
)
def test_pluralize_only_omits_s_for_exactly_one(n, word, expected):
    assert pluralize(n, word) == expected


@pytest.mark.parametrize("period", [0, 1, 12, 100, 202401, 999912])
def test_month_param_round_trips_through_html_month_input_format(period):
    if period == 0:
        assert parse_month_param("") == 0
        return
    assert parse_month_param(format_month_param(period)) == period


@pytest.mark.parametrize(
    "period, expected",
    [
        (202401, "2024-01"),
        (190001, "1900-01"),
        (999912, "9999-12"),
    ],
)
def test_format_month_param_pads_to_four_digit_year_and_two_digit_month(period, expected):
    assert format_month_param(period) == expected


def test_aggregate_plays_sorts_by_descending_count():
    plays = [
        {"name": "A", "singer": "X"},
        {"name": "B", "singer": "Y"},
        {"name": "A", "singer": "X"},
        {"name": "B", "singer": "Y"},
        {"name": "B", "singer": "Y"},
    ]
    assert aggregate_plays(plays) == [("B", "Y", 3), ("A", "X", 2)]


def test_aggregate_plays_treats_missing_singer_key_as_none_not_a_crash():
    plays = [{"name": "A"}, {"name": "A"}]
    assert aggregate_plays(plays) == [("A", None, 2)]


def test_fts_match_query_escapes_embedded_double_quotes_for_fts5():
    query = fts_match_query(['say "hi"'])
    assert query == '"say ""hi"""*'


def test_fts_match_query_ands_multiple_words_together():
    query = fts_match_query(["foo", "bar"])
    assert query == '"foo"* AND "bar"*'


def test_fts_match_query_restricts_every_term_to_one_column():
    query = fts_match_query(["foo", "bar"], column="name")
    assert query == 'name: "foo"* AND name: "bar"*'


def test_most_listened_next_href_omits_month_bounds_when_period_unset():
    href = most_listened_next_href("/most-listened/more", 30, 100, 0, 0)
    assert href == "/most-listened/more?offset=30&max_plays=100&start_month=&end_month="


def test_most_listened_next_href_includes_formatted_month_bounds_when_set():
    href = most_listened_next_href("/most-listened/more", 0, 100, 202401, 202412)
    assert "start_month=2024-01" in href
    assert "end_month=2024-12" in href
