"""Build shipyard.json: one PAX's 112 tracker numbers for a TRMNL display.

Reads the F3 South Cary attendance file the stats site uses, applies the 112 rule
(12 posts and 1 Q in a calendar month), and writes a small JSON file.

Usage:  python build_feed.py [output_path]
Env:    PAX   name exactly as it appears on the stats site (default: Shipyard)
"""
import calendar
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
import zoneinfo


URL = "https://f3southcary.com/stats/data/attendance.parquet"
PAX = os.environ.get("PAX", "Shipyard")
POSTS_GOAL = 12
Q_GOAL = 1
TZ = zoneinfo.ZoneInfo("America/New_York")

# The F3 South Cary Q sheet (must be viewable by anyone with the link).
# Each day tab has an "AO" header row, then one row per date with the Q names under each AO.
Q_SHEET_ID = os.environ.get("Q_SHEET_ID", "1ykUjg88zXPzdjRzKXNeg-3ftGm-1_KT4A5IQ1hy5S9Y")
Q_SHEET_TABS = {
    "Monday": 1067540258,
    "Tuesday": 1309770370,
    "Wednesday": 1972411165,
    "Thursday": 601144444,
    "Friday": 1035187950,
    "Saturday": 2065872098,
}
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})")


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def next_month(d):
    return dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def mon_sat_days_left(today):
    """Days left in the month after today, counting Monday through Saturday only."""
    last = calendar.monthrange(today.year, today.month)[1]
    return sum(
        1
        for day in range(today.day + 1, last + 1)
        if dt.date(today.year, today.month, day).weekday() != 6  # 6 = Sunday
    )


def compute(rows, today):
    if not rows:
        sys.exit(f"No attendance rows found for PAX '{PAX}'. Check the spelling.")

    by_month = {m: (p, q) for m, p, q in rows}
    first = dt.date(int(rows[0][0][:4]), int(rows[0][0][5:]), 1)
    this_month = dt.date(today.year, today.month, 1)

    # Every calendar month from the first post up to and including this month.
    months, cur = [], first
    while cur <= this_month:
        k = month_key(cur)
        posts, qs = by_month.get(k, (0, 0))
        months.append(
            {
                "month": k,
                "posts": posts,
                "qs": qs,
                "passed": posts >= POSTS_GOAL and qs >= Q_GOAL,
                "current": cur == this_month,
            }
        )
        cur = next_month(cur)

    completed = [m for m in months if not m["current"]]
    now = months[-1]

    longest = run = 0
    for m in completed:
        run = run + 1 if m["passed"] else 0
        longest = max(longest, run)
    streak = 0
    for m in reversed(completed):
        if not m["passed"]:
            break
        streak += 1

    days_left = calendar.monthrange(today.year, today.month)[1] - today.day
    workdays_left = mon_sat_days_left(today)
    need_posts = max(0, POSTS_GOAL - now["posts"])
    need_qs = max(0, Q_GOAL - now["qs"])
    blown = False
    if now["passed"]:
        status = "Done early" if days_left > 0 else "Done"
    else:
        bits = []
        if need_posts:
            bits.append(f"{need_posts} post{'s' * (need_posts != 1)}")
        if need_qs:
            bits.append(f"{need_qs} Q")
        need = " + ".join(bits)
        # One workout a day, and a Q is also a post, so the days needed is the larger of the two.
        blown = max(need_posts, need_qs) > workdays_left
        day_word = "day" if workdays_left == 1 else "days"
        if blown:
            status = f"Need {need} in {workdays_left} {day_word} - YOU BLEW IT!"
        else:
            status = f"Need {need} ({workdays_left} {day_word} remaining)"

    feed = {
        "pax": PAX,
        "month": now["month"],
        "month_label": dt.date(today.year, today.month, 1).strftime("%b %Y").upper(),
        "posts": now["posts"],
        "qs": now["qs"],
        "posts_goal": POSTS_GOAL,
        "q_goal": Q_GOAL,
        "passed": now["passed"],
        "status": status,
        "days_left": days_left,
        "workdays_left": workdays_left,
        "blown": blown,
        "posts_over": max(0, now["posts"] - POSTS_GOAL),
        "months_112": sum(m["passed"] for m in completed),
        "streak_current": streak,
        "streak_longest": longest,
        "months_hit_posts": sum(m["posts"] >= POSTS_GOAL for m in completed),
        "months_hit_q": sum(m["qs"] >= Q_GOAL for m in completed),
        "completed_months": len(completed),
        "as_of": today.strftime("%b %-d, %Y"),
    }
    return feed


def last_post_text(last, today):
    """'Today', 'Yesterday', or the date as m/d."""
    if last is None:
        return "None yet"
    if last == today:
        return "Today"
    if last == today - dt.timedelta(days=1):
        return "Yesterday"
    return f"{last.month}/{last.day}"


def fetch_q_tab(gid):
    url = f"https://docs.google.com/spreadsheets/d/{Q_SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "trmnl-112-feed"})
    last_exc = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2)
    raise last_exc


def parse_day_tab(text, pax):
    """Find every date this PAX is signed up to Q on one day tab.

    Layout: a header row with "AO" in column B and the AO names across; below it, one row
    per date (m/d/yyyy in column B) with the Q name under each AO.

    Returns (entries, last_date): entries is a list of (date, ao_name); last_date is the
    latest date listed on the tab, or None if no dates were found.
    """
    name_re = re.compile(re.escape(pax), re.I)  # any cell that contains the name, any capitalization
    ao_row, entries, last = None, [], None
    for row in csv.reader(io.StringIO(text)):
        cells = [" ".join(c.split()) for c in row]
        if ao_row is None:
            if any(c.upper() == "AO" for c in cells[:2]):
                ao_row = cells
            continue
        date_col, m = None, None
        for idx, c in enumerate(cells[:2]):
            m = DATE_RE.fullmatch(c)
            if m:
                date_col = idx
                break
        if not m:
            continue
        year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        try:
            day = dt.date(year, int(m[1]), int(m[2]))
        except ValueError:
            continue
        last = day if last is None else max(last, day)
        for idx in range(date_col + 1, len(cells)):
            if name_re.search(cells[idx]):
                entries.append((day, ao_row[idx] if idx < len(ao_row) else ""))
    return entries, last


def read_q_schedule(pax):
    """Read the Monday-Saturday tabs. Returns (entries, covered_to).

    covered_to is the earliest of the tabs' last dates, so "not signed up" is only claimed
    for dates every tab actually lists. Any tab that can't be read raises an error.
    """
    entries, ends = [], []
    for name, gid in Q_SHEET_TABS.items():
        tab_entries, last = parse_day_tab(fetch_q_tab(gid), pax)
        if last is None:
            raise ValueError(f"no dates found on the {name} tab")
        entries += tab_entries
        ends.append(last)
    return entries, min(ends)


def next_q(entries, today):
    """The next day after today, in today's month, that the PAX is signed up to Q."""
    future = sorted(
        (d, ao) for d, ao in entries
        if d > today and (d.year, d.month) == (today.year, today.month)
    )
    return future[0] if future else None


def q_box_lines(found, covered_to, today, error=None):
    """Text lines for the 'next Q' box."""
    if error:
        return ["Q sheet unavailable"]
    if found:
        d, ao = found
        lines = [f"Next Q on {d.month}/{d.day}"]
        if ao:
            lines.append(f"({ao})")
        return lines
    if covered_to is None:
        return ["Q sheet unreadable"]
    month_end = dt.date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    if covered_to < month_end:
        # The sheet only lists the next week or two, so "none" would be a guess.
        return ["No Q signed up yet", f"(sheet shows through {covered_to.month}/{covered_to.day})"]
    return ["You're not signed up to Q", "again this month"]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "shipyard.json"
    today = dt.datetime.now(TZ).date()

    with tempfile.TemporaryDirectory() as tmp:
        local = os.environ.get("ATTENDANCE_FILE")  # optional: use a local copy instead of downloading
        if not local:
            local = os.path.join(tmp, "attendance.parquet")
            req = urllib.request.Request(URL, headers={"User-Agent": "trmnl-112-feed"})
            with urllib.request.urlopen(req, timeout=60) as r, open(local, "wb") as f:
                f.write(r.read())
        import duckdb

        rows = duckdb.connect().execute(
            """
            select strftime(date_trunc('month', date), '%Y-%m') as month,
                   count(distinct event_id)::int as posts,
                   coalesce(sum(q), 0)::int as qs
            from read_parquet(?)
            where pax = ?
            group by 1 order by 1
            """,
            [local, PAX],
        ).fetchall()
        last_post = duckdb.connect().execute(
            "select max(date) from read_parquet(?) where pax = ?", [local, PAX]
        ).fetchone()[0]
        if isinstance(last_post, dt.datetime):
            last_post = last_post.date()

    feed = compute(rows, today)
    feed["last_post"] = last_post.isoformat() if last_post else None
    feed["last_post_text"] = last_post_text(last_post, today)

    # Next Q from the Q sheet. A sheet problem must not stop the rest of the feed.
    entries, covered_to, q_error = [], None, None
    try:
        entries, covered_to = read_q_schedule(PAX)
    except Exception as exc:  # noqa: BLE001
        q_error = str(exc)[:120]
        print(f"WARNING: could not read the Q sheet: {q_error}")
    found = next_q(entries, today)
    feed["next_q"] = {"date": found[0].isoformat(), "ao": found[1]} if found else None
    feed["q_box_lines"] = q_box_lines(found, covered_to, today, q_error)
    feed["q_sheet_covers_through"] = covered_to.isoformat() if covered_to else None
    feed["q_sheet_error"] = q_error

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(feed, f, indent=2)
    print(json.dumps(feed, indent=2))

    # Also draw the picture TRMNL's Image Display plugin shows (docs/shipyard.png).
    # A drawing problem should not stop the JSON from publishing.
    try:
        from render_png import render

        png_path = os.path.join(os.path.dirname(os.path.abspath(out_path)), "shipyard.png")
        render(feed, png_path)
        print(f"Wrote {png_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not draw PNG: {exc}")


if __name__ == "__main__":
    main()
