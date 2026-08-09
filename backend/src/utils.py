from collections import defaultdict


def aggregate_plays(plays: list) -> list[tuple[str, str | None, int]]:
    counts: dict[tuple, int] = defaultdict(int)
    for p in plays:
        name = p["name"] if "name" in p.keys() else ""
        singer = p["singer"] if "singer" in p.keys() else None
        counts[(name, singer)] += 1
    return sorted(
        [(name, singer, count) for (name, singer), count in counts.items()],
        key=lambda x: -x[2],
    )


def parse_month_param(value: str) -> int:
    """Parses a native <input type="month"> value ("YYYY-MM") into the
    YYYYMM integer the *_play_counts tables key on (see
    library/service.py's ensure_play_count_migrations) - e.g. "2024-08" ->
    202408. Empty string (the "no bound on this side" case, same
    convention as the old start_year/end_year=0) maps to 0."""
    return int(value.replace("-", "")) if value else 0


def format_month_param(period: int) -> str:
    """The inverse of parse_month_param - YYYYMM back to "YYYY-MM", for
    populating an <input type="month">'s value/min/max attributes."""
    return f"{period // 100:04d}-{period % 100:02d}"


def fts_match_query(words: list[str], column: str | None = None) -> str:
    """Build an FTS5 MATCH query from user-typed words: each word becomes a
    quoted prefix term (so "day" matches "Daytime"), AND'd together. Bareword
    terms match against any indexed column. Pass `column` to restrict every
    term to just that column instead (FTS5's `col: term` syntax) - e.g. so a
    track search for "car" doesn't also surface every track by an artist
    named "Cartoon", which an any-column search would."""
    prefix = f"{column}: " if column else ""
    terms = [f'{prefix}"{word.replace(chr(34), chr(34) * 2)}"*' for word in words]
    return " AND ".join(terms)
