#!/usr/bin/env python3
"""Generate donut-chart SVGs for the GitHub profile README (stdlib only).

Reads public, non-fork repositories through the GitHub API and writes:
  assets/languages.svg  - languages by amount of code
  assets/activity.svg   - repositories by time since last push
"""

import json
import math
import os
from datetime import datetime, timezone
from html import escape
from urllib.request import Request, urlopen

USER = os.environ.get("GH_USER", "nickaigi")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = "assets"

LANG_COLORS = {
    "Python": "#3572A5",
    "Lua": "#4f8fd6",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Kotlin": "#A97BFF",
    "Java": "#b07219",
    "HTML": "#e34c26",
    "CSS": "#8e63c9",
    "Shell": "#89e051",
    "C": "#8a8a8a",
    "Vim Script": "#199f4b",
    "Jupyter Notebook": "#DA5B0B",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "SCSS": "#c6538c",
}
FALLBACK = ["#2f81f7", "#3fb950", "#d29922", "#db61a2", "#a371f7", "#f0883e", "#39c5cf"]


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-charts"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    with urlopen(
        Request("https://api.github.com" + path, headers=headers), timeout=30
    ) as r:
        return json.load(r)


def owned_repos():
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            return [r for r in repos if not r["fork"]]
        page += 1


def donut(title, items, center_big, center_small):
    """items: list of (label, value, color). Returns an SVG string."""
    total = sum(v for _, v, _ in items) or 1
    r, sw = 68, 26
    circ = 2 * math.pi * r
    cx, cy = 110, 128
    arcs, legend, cum = [], [], 0.0
    for i, (label, value, color) in enumerate(items):
        frac = value / total
        dash = max(frac * circ - 2, 0.5)
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" stroke-dashoffset="{-cum * circ:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        y = 82 + i * 26
        legend.append(
            f'<rect x="230" y="{y - 11}" width="12" height="12" rx="3" fill="{color}"/>'
            f'<text x="250" y="{y}" font-size="14">{escape(label)}</text>'
            f'<text x="450" y="{y}" font-size="14" text-anchor="end" class="muted">{frac * 100:.1f}%</text>'
        )
        cum += frac
    height = max(260, 82 + len(items) * 26 + 20)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" viewBox="0 0 480 {height}" role="img" aria-label="{escape(title)}">
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#1f2328}}
.muted{{fill:#59636e}}.track{{stroke:#d1d9e0}}
@media (prefers-color-scheme:dark){{text{{fill:#f0f6fc}}.muted{{fill:#9198a1}}.track{{stroke:#3d444d}}}}
</style>
<text x="24" y="36" font-size="18" font-weight="600">{escape(title)}</text>
<circle class="track" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke-width="{sw}"/>
{chr(10).join(arcs)}
<text x="{cx}" y="{cy + 6}" font-size="26" font-weight="700" text-anchor="middle">{escape(str(center_big))}</text>
<text x="{cx}" y="{cy + 26}" font-size="12" text-anchor="middle" class="muted">{escape(center_small)}</text>
{chr(10).join(legend)}
</svg>
"""


def language_chart(bytes_by_lang):
    ranked = sorted(bytes_by_lang.items(), key=lambda kv: kv[1], reverse=True)
    top, rest = ranked[:7], sum(v for _, v in ranked[7:])
    items = []
    for i, (name, value) in enumerate(top):
        items.append((name, value, LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])))
    if rest:
        items.append(("Other", rest, "#8b949e"))
    return donut("Languages by code size", items, len(ranked), "languages")


def activity_chart(pushed_dates, now=None):
    now = now or datetime.now(timezone.utc)
    buckets = [
        ("Last 3 months", 92, "#3fb950"),
        ("3 to 12 months", 365, "#2f81f7"),
        ("1 to 3 years", 1095, "#d29922"),
        ("Over 3 years", 10**9, "#8b949e"),
    ]
    counts = [0] * len(buckets)
    for d in pushed_dates:
        age = (now - d).days
        for i, (_, limit, _) in enumerate(buckets):
            if age <= limit:
                counts[i] += 1
                break
    items = [(b[0], c, b[2]) for b, c in zip(buckets, counts) if c]
    return donut(
        "Repositories by last push", items, len(pushed_dates), "original repos"
    )


def main():
    repos = owned_repos()
    totals = {}
    for repo in repos:
        try:
            for lang, n in api(f"/repos/{USER}/{repo['name']}/languages").items():
                totals[lang] = totals.get(lang, 0) + n
        except Exception as exc:  # keep going if one repo fails
            print(f"skip {repo['name']}: {exc}")
    dates = [
        datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        for r in repos
        if r.get("pushed_at")
    ]
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/languages.svg", "w", encoding="utf-8") as f:
        f.write(language_chart(totals))
    with open(f"{OUT}/activity.svg", "w", encoding="utf-8") as f:
        f.write(activity_chart(dates))
    print(f"{len(repos)} repos, {len(totals)} languages")


if __name__ == "__main__":
    main()
