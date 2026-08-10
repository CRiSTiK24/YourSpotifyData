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
    return int(value.replace("-", "")) if value else 0


def format_month_param(period: int) -> str:
    return f"{period // 100:04d}-{period % 100:02d}"


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
