import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import math

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USER", "Madhu-204")

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


def fetch_contributions():
    payload = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Stats-Generator",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]
    days = []
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            days.append({"count": day["contributionCount"], "date": day["date"]})
    return total, days


def level(count):
    if count == 0:
        return 0
    if count <= 3:
        return 1
    if count <= 6:
        return 2
    if count <= 9:
        return 3
    return 4


COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS_LABEL = ["", "Mon", "", "Wed", "", "Fri", ""]

CELL = 11
GAP = 3
PITCH = CELL + GAP
LEFT_PAD = 40
TOP_PAD = 24
RIGHT_PAD = 16
BOTTOM_PAD = 8


def generate_activity_svg(total, days):
    if not days:
        return ""

    first_date = datetime.strptime(days[0]["date"], "%Y-%m-%d")
    start_weekday = first_date.weekday()

    date_map = {d["date"]: d["count"] for d in days}

    today = datetime.utcnow().date()
    end_date = today

    start_date = end_date - timedelta(days=364)
    start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)

    weeks = []
    current = start_date
    while current <= end_date:
        week = []
        for i in range(7):
            d = current + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            cnt = date_map.get(ds, 0) if ds <= end_date.strftime("%Y-%m-%d") else -1
            week.append(cnt)
        weeks.append((current, week))
        current += timedelta(days=7)

    cols = len(weeks)
    svg_w = LEFT_PAD + cols * PITCH + RIGHT_PAD
    svg_h = TOP_PAD + 7 * PITCH + BOTTOM_PAD

    rects = []

    month_positions = {}
    for ci, (week_start, week) in enumerate(weeks):
        for ri, cnt in enumerate(week):
            if cnt < 0:
                continue
            x = LEFT_PAD + ci * PITCH
            y = TOP_PAD + ri * PITCH
            c = COLORS[level(cnt)]
            rects.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" ry="2" fill="{c}"><title>{cnt} contributions on {(week_start + timedelta(days=ri)).strftime("%b %d, %Y")}</title></rect>')

        m = week_start.month
        if m not in month_positions:
            month_positions[m] = ci

    month_labels = []
    for m, ci in month_positions.items():
        x = LEFT_PAD + ci * PITCH
        month_labels.append(f'<text x="{x}" y="14" class="month">{MONTHS[m]}</text>')

    day_labels = []
    for i, label in enumerate(DAYS_LABEL):
        if label:
            y = TOP_PAD + i * PITCH + CELL - 1
            day_labels.append(f'<text x="30" y="{y}" class="day" text-anchor="end">{label}</text>')

    rect_str = "\n    ".join(rects)
    month_str = "\n    ".join(month_labels)
    day_str = "\n    ".join(day_labels)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
  <style>
    .month {{ fill: #8b949e; font-size: 10px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .day {{ fill: #8b949e; font-size: 9px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .total {{ fill: #e6edf3; font-size: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-weight: 600; }}
  </style>
  <rect width="{svg_w}" height="{svg_h}" rx="6" ry="6" fill="#0d1117"/>
  <text x="{svg_w - 12}" y="16" class="total" text-anchor="end">{total} contributions in the last year</text>
  {month_str}
  {day_str}
  {rect_str}
</svg>'''
    return svg


def generate_streak_svg(total, days):
    date_counts = {}
    for d in days:
        date_counts[d["date"]] = d["count"]

    today = datetime.utcnow().date()
    today_str = today.strftime("%Y-%m-%d")

    def has_contributed(dt_str):
        return date_counts.get(dt_str, 0) > 0

    current_streak = 0
    d = today
    while has_contributed(d.strftime("%Y-%m-%d")):
        current_streak += 1
        d -= timedelta(days=1)

    longest_streak = 0
    streak = 0
    sorted_dates = sorted(date_counts.keys())
    if sorted_dates:
        start = datetime.strptime(sorted_dates[0], "%Y-%m-%d").date()
        end = datetime.strptime(sorted_dates[-1], "%Y-%m-%d").date()
        d = start
        while d <= end:
            if has_contributed(d.strftime("%Y-%m-%d")):
                streak += 1
                longest_streak = max(longest_streak, streak)
            else:
                streak = 0
            d += timedelta(days=1)

    svg_w = 480
    svg_h = 130

    def stat_block(x, value, label):
        return f'''<g transform="translate({x}, 20)">
    <text x="80" y="30" class="num" text-anchor="middle">{value}</text>
    <text x="80" y="52" class="label" text-anchor="middle">{label}</text>
  </g>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
  <style>
    .num {{ fill: #39d353; font-size: 36px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-weight: 700; }}
    .label {{ fill: #8b949e; font-size: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .title {{ fill: #e6edf3; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-weight: 600; }}
  </style>
  <rect width="{svg_w}" height="{svg_h}" rx="6" ry="6" fill="#0d1117"/>
  <text x="{svg_w / 2}" y="18" class="title" text-anchor="middle">GitHub Streak</text>
  {stat_block(0, current_streak, "Current Streak")}
  {stat_block(160, longest_streak, "Longest Streak")}
  {stat_block(320, total, "Total Contributions")}
</svg>'''
    return svg


def main():
    total, days = fetch_contributions()
    print(f"Total contributions: {total}")
    print(f"Days with data: {len(days)}")

    activity = generate_activity_svg(total, days)
    streak = generate_streak_svg(total, days)

    os.makedirs("dist", exist_ok=True)

    with open("dist/activity.svg", "w", encoding="utf-8") as f:
        f.write(activity)
    print("Generated dist/activity.svg")

    with open("dist/streak.svg", "w", encoding="utf-8") as f:
        f.write(streak)
    print("Generated dist/streak.svg")


if __name__ == "__main__":
    main()
