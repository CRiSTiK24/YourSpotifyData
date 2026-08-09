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


def _month_chip(year: int, month: int, count: int, base_href: str, key_prefix: str, sep: str) -> str:
    color = _cell_color(count)
    href = base_href + sep + urlencode({f"hm_{key_prefix}": f"{year}-{month}"})
    tooltip = f"{MONTHS[month - 1]} {year}: {count} play{'s' if count != 1 else ''}"
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
    """Every year's 12-month breakdown shown at once, stacked, rather than
    a years -> months click-through (the old _chip_rows_html drill-down) -
    with real width available beside the header image on desktop (see
    .hm-month-chip's flex-fill sizing in style.css), hiding all but one
    year behind extra clicks wasted that space instead of using it to show
    more at a glance. Most recent year first. A year's label is itself a
    filter link (narrows the track list to that whole year, exactly what
    selecting a year used to do); each month chip drills straight into
    that month's day/week grid (see _day_grid_html)."""
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
            f"title='{year_total} play{'s' if year_total != 1 else ''} in {year}'>{year}</a>"
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
    """Days-of-week as columns, weeks as rows - the familiar calendar-grid
    orientation. Used to be transposed (weeks as columns) to stay narrow
    enough to sit beside the hero image, back when the grid's own size was
    fixed regardless of available width; now that .heatmap-wrap fills
    whatever width it's given and only caps height (see style.css), that
    constraint doesn't apply and the natural orientation reads better."""
    sep = "&" if "?" in base_href else "?"
    first_weekday, num_days = calendar.monthrange(year, month)
    num_weeks = -(-(first_weekday + num_days) // 7)  # ceil division

    # day_by_week_dow[week][dow] = day number, or None for out-of-month cells
    day_by_week_dow: list[list[int | None]] = [[None] * 7 for _ in range(num_weeks)]
    day_cursor = 1
    for week in range(num_weeks):
        for dow in range(7):
            if (week == 0 and dow < first_weekday) or day_cursor > num_days:
                continue
            day_by_week_dow[week][dow] = day_cursor
            day_cursor += 1

    # Width/font-size are left entirely to CSS (table-layout:fixed + the
    # .hm-day-cell/.heatmap-wrap th rules) rather than inline styles here -
    # inline font-size would override the stylesheet's clamp() and stop it
    # scaling with the panel, and a fixed header width would stop lining
    # up with cells that grow/shrink to fill available space.
    header = f"<th><a href='{escape(back_href)}' title='Back to months' " \
        f"style='color:{Palette.TEXT}'>‹</a></th>" + "".join(
        f"<th>{DAYS_OF_WEEK[dow][0]}</th>" for dow in range(7)
    )
    rows = ""
    for week in range(num_weeks):
        cells = f"<td class='hm-day-label'>{week + 1}</td>"
        for dow in range(7):
            d = day_by_week_dow[week][dow]
            if d is None:
                cells += "<td style='padding:1px'><span class='hm-day-empty'></span></td>"
                continue
            c = day_counts.get(d, 0)
            color = _cell_color(c)
            border = f"2px solid {Palette.TEXT}" if selected_day == d else "2px solid transparent"
            tooltip = f"{MONTHS[month - 1]} {d}, {year}: {c} play{'s' if c != 1 else ''}"
            href = base_href + sep + urlencode(
                {f"hm_{key_prefix}": f"{year}-{month}", f"hm_{key_prefix}_d": d}
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
    """Formats a build_heatmap_html result tuple ((year, month|None,
    day|None, plays)) into "2026" / "Aug 2026" / "Aug 15, 2026" - shared
    by every caller that shows what period a heatmap selection filtered
    down to (previously duplicated in each of artists/albums/playlists'
    routers)."""
    year, month, day, _plays = result
    if month is None:
        return str(year)
    return f"{MONTHS[month - 1]} {day}, {year}" if day else f"{MONTHS[month - 1]} {year}"


def build_heatmap_html(
    history: list[sqlite3.Row],
    key_prefix: str,
    request: Request,
) -> tuple[str, tuple | None, str]:
    """A compact-but-growing heatmap, sized to sit beside the header
    image/title (see .detail-header-top in style.css / the *_top routers).
    Two levels: an always-visible overview (every year's 12-month
    breakdown at once, see _years_overview_html) and a days/weeks grid for
    whichever month gets clicked (see _day_grid_html) - the '‹' in the
    grid's corner returns to the overview.

    Returns (heatmap_html, result, base_href). result is None at the
    years/months levels, and (year, month, day|None, plays) once a month
    is picked (day/week grid level) - plays being that period's play
    rows, for the caller to filter its own list with (see period_label
    above). base_href is this page's URL with all heatmap selection state
    (`hm_*` params) stripped, for a caller-rendered "clear filter" link
    back to the unfiltered view."""
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
        # Picking a year (not just a month/day) filters the list too, same
        # as any other level - month is None here, which period_label and
        # every caller's `if result:` branch already handle.
        year_plays = [p for m in range(1, 13) for p in by_month.get((sel_year, m), [])]
        result = (sel_year, None, None, year_plays)
    else:
        result = None
    return html, result, base_href
