#!/usr/bin/env python3
"""Refresh the public GitHub and GitLab activity snapshot for Said's portfolio."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "activity.json"
GITHUB_USER = "cielhaidir"
GITLAB_USER = "cielhaidir"
YEARS = range(2024, datetime.now(timezone.utc).year + 1)
USER_AGENT = "saidhr-portfolio-activity-sync/1.0"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read()


def github_calendar(year: int) -> dict[str, int]:
    url = (
        f"https://github.com/users/{GITHUB_USER}/contributions"
        f"?from={year}-01-01&to={year}-12-31"
    )
    html = fetch(url).decode("utf-8")
    calendar: dict[str, int] = {}
    pattern = re.compile(
        r'data-date="(?P<date>\d{4}-\d{2}-\d{2})"[^>]*data-level="(?P<level>\d+)"'
    )
    for match in pattern.finditer(html):
        day = match.group("date")
        if not day.startswith(f"{year}-"):
            continue
        nearby = html[match.end() : match.end() + 700]
        count_match = re.search(r"(\d[\d,]*) contribution", nearby)
        level = int(match.group("level"))
        calendar[day] = (
            int(count_match.group(1).replace(",", ""))
            if count_match
            else (0 if level == 0 else level)
        )

    current = date(year, 1, 1)
    final = date(year, 12, 31)
    while current <= final:
        calendar.setdefault(current.isoformat(), 0)
        current += timedelta(days=1)
    return calendar


def gitlab_calendar() -> dict[str, int]:
    url = f"https://gitlab.com/users/{GITLAB_USER}/calendar.json"
    raw = json.loads(fetch(url).decode("utf-8"))
    return {day: int(count) for day, count in raw.items()}


def main() -> int:
    github: dict[str, int] = {}
    for year in YEARS:
        github.update(github_calendar(year))
    gitlab = gitlab_calendar()
    snapshot = {
        "github": dict(sorted(github.items())),
        "gitlab": dict(sorted(gitlab.items())),
        "meta": {
            "github": f"https://github.com/{GITHUB_USER}",
            "gitlab": f"https://gitlab.com/{GITLAB_USER}",
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "Public GitHub contribution pages and GitLab calendar endpoint",
        },
    }
    serialized = json.dumps(snapshot, indent=2) + "\n"
    previous = OUT.read_text() if OUT.exists() else ""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized)
    print(
        json.dumps(
            {
                "changed": serialized != previous,
                "github_total": sum(github.values()),
                "gitlab_total": sum(gitlab.values()),
                "combined_total": sum(github.values()) + sum(gitlab.values()),
                "github_years": sorted({day[:4] for day in github}),
                "gitlab_years": sorted({day[:4] for day in gitlab}),
                "output": str(OUT),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
