import calendar
import sqlite3
from collections import defaultdict
from html import escape
from urllib.parse import urlencode

from fastapi import Request

from src.constants import COLORS, DAYS_OF_WEEK, MONTHS
from src.palette import Palette


_THRESHOLDS = [50, 100, 200]  # absolute play-count breakpoints, low to high


def _cell_color(count: int) -> str:
    if count == 0:
        return COLORS[0]
    for i, threshold in enumerate(_THRESHOLDS, start=1):
        if count <= threshold:
            return COLORS[i]
    return COLORS[-1]


def _month_grid_html(
    counts: dict,
    years: list,
    selected: tuple | None,
    base_href: str,
    key_prefix: str,
) -> str:
    sep = "&" if "?" in base_href else "?"
    # Once a month is selected, collapse to just that year's column instead
    # of showing every year, freeing up the horizontal space the day-level
    # grid needs to sit alongside it without crowding/scrolling.
    display_years = [selected[0]] if selected else years
    corner = f"<a href='{escape(base_href)}' title='All years'>‹</a>" if selected else ""
    header = f"<th class='row-label'>{corner}</th>" + "".join(f"<th>{y}</th>" for y in display_years)
    rows = ""
    for m in range(1, 13):
        cells = f"<td style='font-size:11px;color:{Palette.TEXT};padding-right:6px'>{MONTHS[m - 1]}</td>"
        for year in display_years:
            c = counts.get((year, m), 0)
            color = _cell_color(c)
            border = f"2px solid {Palette.TEXT}" if selected == (year, m) else "2px solid transparent"
            tooltip = f"{MONTHS[m - 1]} {year}: {c} play{'s' if c != 1 else ''}"
            href = base_href + sep + urlencode({f"hm_{key_prefix}": f"{year}-{m}"})
            text = "&nbsp;" if c == 0 else str(c)
            cells += (
                f"<td style='padding:2px'>"
                f"<a class='hm-cell' href='{escape(href)}' title='{escape(tooltip)}' "
                f"style='background:{color};border:{border}'>{text}</a></td>"
            )
        rows += f"<tr>{cells}</tr>"
    return (
        f"<div class='heatmap-wrap'><table>"
        f"<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _day_grid_html(
    year: int,
    month: int,
    day_counts: dict,
    selected_day: int | None,
    base_href: str,
    key_prefix: str,
) -> str:
    sep = "&" if "?" in base_href else "?"
    first_weekday, num_days = calendar.monthrange(year, month)
    header = "<th style='width:30px'></th>" + "".join(
        f"<th style='width:38px;text-align:center;font-size:11px;color:{Palette.TEXT}'>{d}</th>"
        for d in DAYS_OF_WEEK
    )
    day_cursor = 1
    rows = ""
    week = 1
    while day_cursor <= num_days:
        cells = f"<td style='font-size:11px;color:{Palette.TEXT};padding-right:4px'>W{week}</td>"
        for dow in range(7):
            if (week == 1 and dow < first_weekday) or day_cursor > num_days:
                cells += "<td style='padding:2px'><span style='display:block;width:28px;height:28px'></span></td>"
            else:
                d = day_cursor
                c = day_counts.get(d, 0)
                color = _cell_color(c)
                border = f"2px solid {Palette.TEXT}" if selected_day == d else "2px solid transparent"
                tooltip = f"{MONTHS[month - 1]} {d}, {year}: {c} play{'s' if c != 1 else ''}"
                href = base_href + sep + urlencode(
                    {f"hm_{key_prefix}": f"{year}-{month}", f"hm_{key_prefix}_d": d}
                )
                text = "&nbsp;" if c == 0 else str(c)
                cells += (
                    f"<td style='padding:2px'>"
                    f"<a class='hm-day-cell' href='{escape(href)}' title='{escape(tooltip)}' "
                    f"style='background:{color};border:{border}'>{text}</a></td>"
                )
                day_cursor += 1
                if day_cursor > num_days:
                    for _ in range(dow + 1, 6):
                        cells += "<td style='padding:2px'><span style='display:block;width:28px;height:28px'></span></td>"
                    break
        rows += f"<tr>{cells}</tr>"
        week += 1
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
        by_month[(year, month)].append(entry)
    years = sorted({y for y, _ in counts})
    return dict(counts), dict(by_month), years


def build_heatmap_html(
    history: list[sqlite3.Row],
    key_prefix: str,
    request: Request,
) -> tuple[str, tuple | None]:
    counts, by_month, years = build_heatmap_data(history)
    if not counts:
        return "<p class='info'>No play history to display.</p>", None

    qp = dict(request.query_params)
    base_href = (
        str(request.url.path)
        + "?"
        + urlencode({k: v for k, v in qp.items() if not k.startswith("hm_")})
    )

    sel_month_key = qp.get(f"hm_{key_prefix}", "")
    sel_month = tuple(int(x) for x in sel_month_key.split("-")) if sel_month_key else None

    if not sel_month:
        grid = _month_grid_html(counts, years, None, base_href, key_prefix)
        return grid, None

    sel_year, sel_month_num = sel_month
    month_plays = by_month.get((sel_year, sel_month_num), [])

    day_counts: dict[int, int] = defaultdict(int)
    by_day: dict[int, list] = defaultdict(list)
    for p in month_plays:
        day_counts[p["day"]] += 1
        by_day[p["day"]].append(p)

    sel_day_key = qp.get(f"hm_{key_prefix}_d", "")
    sel_day = int(sel_day_key) if sel_day_key else None

    month_label = f"{MONTHS[sel_month_num - 1]} {sel_year}"
    month_grid = _month_grid_html(counts, years, sel_month, base_href, key_prefix)
    day_grid = _day_grid_html(
        sel_year, sel_month_num, dict(day_counts), sel_day, base_href, key_prefix
    )

    html = (
        f"<div class='heatmap-cols'>{month_grid}"
        + f"<div><p class='subtitle'>{month_label}</p>{day_grid}</div></div>"
    )

    result = (
        (sel_year, sel_month_num, sel_day, by_day.get(sel_day, []))
        if sel_day
        else (sel_year, sel_month_num, None, month_plays)
    )
    return html, result
