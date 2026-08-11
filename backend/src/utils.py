import calendar
import re
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


def parse_month_param(value: str, *, end: bool = False) -> int:
    """Parses a period boundary as YYYY-MM-DD (native <input type="date">),
    YYYY-MM (native <input type="month">), or the human-typed MM/YYYY,
    DD/MM/YYYY, or YYYY. A bare year has no month of its own, so `end`
    picks which edge of that year it means - January for a start bound,
    December for an end bound - so "2022" as a range on its own still
    covers the whole year."""
    if not value:
        return 0
    parts = re.split(r"[/-]", value.strip())
    try:
        if len(parts) == 1:
            year, month = int(parts[0]), (12 if end else 1)
        elif len(parts) == 2:
            a, b = parts
            year, month = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
        elif len(parts) == 3:
            a, b, c = parts
            # YYYY-MM-DD (native date input) has the year first; the
            # human-typed DD/MM/YYYY has it last - only one of the two
            # outer parts can plausibly be a 4-digit year, so that's
            # enough to tell which order this is without needing to know
            # which input produced it.
            year, month = (int(a), int(b)) if len(a) == 4 else (int(c), int(b))
        else:
            return 0
    except ValueError:
        return 0
    if not (1 <= month <= 12):
        return 0
    return year * 100 + month


def format_month_param(period: int) -> str:
    return f"{period // 100:04d}-{period % 100:02d}"


def _synthesized_date_parts(period: int, *, end: bool) -> tuple[int, int, int] | None:
    if not period:
        return None
    year, month = divmod(period, 100)
    day = calendar.monthrange(year, month)[1] if end else 1
    return year, month, day


def format_date_param_iso(period: int, *, end: bool = False) -> str:
    """Same as format_date_param, but YYYY-MM-DD - the only format a native
    <input type="date"> accepts for its value/min/max attributes (the
    picker itself then displays it in the user's own OS/locale format)."""
    parts = _synthesized_date_parts(period, end=end)
    if not parts:
        return ""
    year, month, day = parts
    return f"{year:04d}-{month:02d}-{day:02d}"


def pluralize(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def most_listened_next_href(
    path: str, offset: int, max_plays: int, start_period: int, end_period: int
) -> str:
    start_month = format_month_param(start_period) if start_period else ""
    end_month = format_month_param(end_period) if end_period else ""
    return f"{path}?offset={offset}&max_plays={max_plays}&start_month={start_month}&end_month={end_month}"


def fts_match_query(words: list[str], column: str | None = None) -> str:
    prefix = f"{column}: " if column else ""
    terms = [f'{prefix}"{word.replace(chr(34), chr(34) * 2)}"*' for word in words]
    return " AND ".join(terms)
