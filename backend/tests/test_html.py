from src.html import card, paginated_fragment, row


def test_row_escapes_html_special_characters_in_track_and_artist_names():
    html = row("<script>alert(1)</script>", "/track/x", "Me & You", "/artist/x")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Me &amp; You" in html


def test_card_escapes_html_special_characters_in_the_hover_tooltip():
    html = card("Playlist", "/playlist/1", hover_tooltip='"><img src=x onerror=alert(1)>')
    assert "onerror=alert(1)>" not in html
    assert "&quot;&gt;&lt;img" in html


def test_paginated_fragment_returns_empty_message_only_on_the_first_page():
    assert (
        paginated_fragment(
            "", offset=0, has_more=False, next_href="/x", empty_message="No plays yet."
        )
        == "No plays yet."
    )
    assert (
        paginated_fragment(
            "", offset=30, has_more=False, next_href="/x", empty_message="No plays yet."
        )
        == ""
    )


def test_paginated_fragment_appends_a_sentinel_only_when_more_rows_remain():
    with_more = paginated_fragment("<div>row</div>", offset=0, has_more=True, next_href="/next")
    without_more = paginated_fragment("<div>row</div>", offset=0, has_more=False, next_href="/next")
    assert "hx-get='/next'" in with_more
    assert "hx-get" not in without_more
