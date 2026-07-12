from src.html import back_link, search_form


def search_form_content() -> str:
    return f"""
{back_link("/")}
<h1>Search</h1>
{search_form("/search", "Search tracks, artists, playlists…")}
"""
