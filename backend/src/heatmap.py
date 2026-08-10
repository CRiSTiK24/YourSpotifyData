import calendar
import sqlite3
from collections import defaultdict
from html import escape
from urllib.parse import urlencode

from fastapi import Request

from src.constants import COLORS, DAYS_OF_WEEK, MONTHS
from src.html import filter_clear_link
from src.palette import Palette
from src.utils import pluralize

_PLAY_COUNT_THRESHOLDS_LOW_TO_HIGH = [50, 100, 200]


def _cell_color(count: int) -> str:
    if count == 0:
        return COLORS[0]
    for i, threshold in enumerate(_PLAY_COUNT_THRESHOLDS_LOW_TO_HIGH, start=1):
        if count <= threshold:
            return COLORS[i]
    return COLORS[-1]


def _month_chip(
    year: int, month: int, count: int, base_href: str, key_prefix: str, sep: str
) -> str:
    color = _cell_color(count)
    href = base_href + sep + urlencode({f"hm_{key_prefix}": f"{year}-{month}"})
    tooltip = f"{MONTHS[month - 1]} {year}: {pluralize(count, 'play')}"
    return (
        f"<a class='hm-month-chip' href='{escape(href)}' title='{escape(tooltip)}' "
        f"style='background:{color}'></a>"
    )


def _years_overview_html(
    years: list[int],
    counts: dict[tuple, int],
    base_href: str,
    key_prefix: str,
    sel_year: int | None,
) -> str:
    sep = "&" if "?" in base_href else "?"
    rows = []
    for year in sorted(years, reverse=True):
        year_total = sum(counts.get((year, m), 0) for m in range(1, 13))
        year_href = base_href + sep + urlencode({f"hm_{key_prefix}_y": year})
        selected_cls = " hm-year-row-selected" if year == sel_year else ""
        months = "".join(
            _month_chip(year, m, counts.get((year, m), 0), base_href, key_prefix, sep)
            for m in range(1, 13)
        )
        rows.append(
            f"<div class='hm-year-row{selected_cls}'>"
            f"<a class='hm-year-row-label' href='{escape(year_href)}' "
            f"title='{pluralize(year_total, 'play')} in {year}'>{year}</a>"
            f"<div class='hm-months-strip'>{months}</div>"
            f"</div>"
        )
    return f"<div class='heatmap-years-overview'>{''.join(rows)}</div>"


def _day_grid_html(
    year: int,
    month: int,
    day_counts: dict,
    selected_day: int | None,
    base_href: str,
    key_prefix: str,
    back_href: str,
) -> str:
    sep = "&" if "?" in base_href else "?"
    first_weekday, num_days = calendar.monthrange(year, month)
    num_weeks = -(-(first_weekday + num_days) // 7)

    day_number_by_week_and_weekday: list[list[int | None]] = [[None] * 7 for _ in range(num_weeks)]
    day_cursor = 1
    for week in range(num_weeks):
        for dow in range(7):
            if (week == 0 and dow < first_weekday) or day_cursor > num_days:
                continue
            day_number_by_week_and_weekday[week][dow] = day_cursor
            day_cursor += 1

    header = (
        f"<th><a href='{escape(back_href)}' title='Back to months' "
        f"style='color:{Palette.TEXT}'>‹</a></th>"
        + "".join(f"<th>{DAYS_OF_WEEK[dow][0]}</th>" for dow in range(7))
    )
    rows = ""
    for week in range(num_weeks):
        cells = f"<td class='hm-day-label'>{week + 1}</td>"
        for dow in range(7):
            d = day_number_by_week_and_weekday[week][dow]
            if d is None:
                cells += "<td style='padding:1px'><span class='hm-day-empty'></span></td>"
                continue
            c = day_counts.get(d, 0)
            color = _cell_color(c)
            border = f"2px solid {Palette.TEXT}" if selected_day == d else "2px solid transparent"
            tooltip = f"{MONTHS[month - 1]} {d}, {year}: {pluralize(c, 'play')}"
            href = (
                base_href
                + sep
                + urlencode({f"hm_{key_prefix}": f"{year}-{month}", f"hm_{key_prefix}_d": d})
            )
            text = "&nbsp;" if c == 0 else str(c)
            cells += (
                f"<td style='padding:1px'>"
                f"<a class='hm-day-cell' href='{escape(href)}' title='{escape(tooltip)}' "
                f"style='background:{color};border:{border}'>{text}</a></td>"
            )
        rows += f"<tr>{cells}</tr>"
    return (
        f"<div class='heatmap-wrap'><table>"
        f"<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def build_heatmap_data(
    history: list[sqlite3.Row],
) -> tuple[dict[tuple, int], dict[tuple, list], list[int]]:
    counts: dict[tuple, int] = defaultdict(int)
    by_month: dict[tuple, list] = defaultdict(list)
    for row in history:
        ts = row["time"]
        year, month, day = int(ts[:4]), int(ts[5:7]), int(ts[8:10])
        counts[(year, month)] += 1
        entry: dict = {"day": day}
        if "name" in row.keys():
            entry["name"] = row["name"]
            entry["singer"] = row["singer"]
            if "album" in row.keys():
                entry["album"] = row["album"]
        by_month[(year, month)].append(entry)
    years = sorted({y for y, _ in counts})
    return dict(counts), dict(by_month), years


def period_label(result: tuple) -> str:
    year, month, day, _plays = result
    if month is None:
        return str(year)
    return f"{MONTHS[month - 1]} {day}, {year}" if day else f"{MONTHS[month - 1]} {year}"


def resolve_period_filter(
    history: list[sqlite3.Row], result: tuple | None, base_href: str
) -> tuple[list, int, str]:
    if result is None:
        return history, len(history), ""
    _, _, _, plays = result
    return plays, len(plays), filter_clear_link(period_label(result), base_href)


def build_heatmap_html(
    history: list[sqlite3.Row],
    key_prefix: str,
    request: Request,
) -> tuple[str, tuple | None, str]:
    qp = dict(request.query_params)
    base_href = (
        str(request.url.path)
        + "?"
        + urlencode({k: v for k, v in qp.items() if not k.startswith("hm_")})
    )
    counts, by_month, years = build_heatmap_data(history)
    if not counts:
        return "<p class='info'>No play history to display.</p>", None, base_href

    sel_month_key = qp.get(f"hm_{key_prefix}", "")
    sel_month = tuple(int(x) for x in sel_month_key.split("-")) if sel_month_key else None

    if sel_month:
        sel_year, sel_month_num = sel_month
        month_plays = by_month.get((sel_year, sel_month_num), [])

        day_counts: dict[int, int] = defaultdict(int)
        by_day: dict[int, list] = defaultdict(list)
        for p in month_plays:
            day_counts[p["day"]] += 1
            by_day[p["day"]].append(p)

        sel_day_key = qp.get(f"hm_{key_prefix}_d", "")
        sel_day = int(sel_day_key) if sel_day_key else None

        html = _day_grid_html(
            sel_year, sel_month_num, dict(day_counts), sel_day, base_href, key_prefix, base_href
        )
        result = (
            (sel_year, sel_month_num, sel_day, by_day.get(sel_day, []))
            if sel_day
            else (sel_year, sel_month_num, None, month_plays)
        )
        return html, result, base_href

    year_param = qp.get(f"hm_{key_prefix}_y", "")
    sel_year = int(year_param) if year_param and int(year_param) in years else None

    html = _years_overview_html(years, counts, base_href, key_prefix, sel_year)
    if sel_year:
        year_plays = [p for m in range(1, 13) for p in by_month.get((sel_year, m), [])]
        result = (sel_year, None, None, year_plays)
    else:
        result = None
    return html, result, base_href
