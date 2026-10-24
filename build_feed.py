"""Build shipyard.json: one PAX's 112 tracker numbers for a TRMNL display.

Reads the F3 South Cary attendance file the stats site uses, applies the 112 rule
(12 posts and 1 Q in a calendar month), and writes a small JSON file.

Usage:  python build_feed.py [output_path]
Env:    PAX   name exactly as it appears on the stats site (default: Shipyard)
"""
import calendar
import datetime as dt
import json
import os
import sys
import tempfile
import urllib.request
import zoneinfo


URL = "https://f3southcary.com/stats/data/attendance.parquet"
PAX = os.environ.get("PAX", "Shipyard")
POSTS_GOAL = 12
Q_GOAL = 1
TZ = zoneinfo.ZoneInfo("America/New_York")


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def next_month(d):
    return dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


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
    need_posts = max(0, POSTS_GOAL - now["posts"])
    need_qs = max(0, Q_GOAL - now["qs"])
    if now["passed"]:
        status = "Done early" if days_left > 0 else "Done"
    else:
        bits = []
        if need_posts:
            bits.append(f"{need_posts} post{'s' * (need_posts != 1)}")
        if need_qs:
            bits.append(f"{need_qs} Q")
        status = "Need " + " + ".join(bits)

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

    feed = compute(rows, today)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(feed, f, indent=2)
    print(json.dumps(feed, indent=2))


if __name__ == "__main__":
    main()
