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


def word_clauses(words: list[str], *columns: str) -> tuple[str, list[str]]:
    parts = []
    params = []
    for word in words:
        col_checks = " OR ".join(f"{col} LIKE ?" for col in columns)
        parts.append(f"({col_checks})")
        params.extend(f"%{word}%" for _ in columns)
    return " AND ".join(parts), params
