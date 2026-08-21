#!/usr/bin/env python3
"""Render db/jobs.db into a static HTML report for GitHub Pages."""

from __future__ import annotations

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.tracker import Tracker  # noqa: E402


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def render(tracker: Tracker) -> str:
    funnel = tracker.funnel_counts()
    recent = tracker.recent_applications(40)
    health = tracker.portal_health()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    funnel_order = [
        "found",
        "queued",
        "applied",
        "manual",
        "skipped",
        "failed",
        "viewed",
        "interview",
        "rejected",
        "offer",
    ]
    funnel_html = "".join(
        f'<div class="stat"><div class="n">{funnel.get(s, 0)}</div><div class="l">{s}</div></div>'
        for s in funnel_order
        if funnel.get(s, 0) or s in ("applied", "interview", "manual", "skipped")
    )

    rows = []
    for r in recent:
        rows.append(
            "<tr>"
            f"<td>{_esc(r.get('updated_at'))}</td>"
            f"<td>{_esc(r.get('portal'))}</td>"
            f"<td>{_esc(r.get('company'))}</td>"
            f"<td><a href='{_esc(r.get('url'))}' target='_blank' rel='noopener'>{_esc(r.get('title'))}</a></td>"
            f"<td>{_esc(r.get('fit_score'))}</td>"
            f"<td><span class='badge'>{_esc(r.get('status'))}</span></td>"
            "</tr>"
        )
    table_body = "\n".join(rows) or "<tr><td colspan='6'>No applications yet.</td></tr>"

    health_rows = []
    for h in health:
        flag = "needs re-auth" if h.get("needs_reauth") else "ok"
        health_rows.append(
            f"<tr><td>{_esc(h.get('portal'))}</td><td>{_esc(flag)}</td>"
            f"<td>{_esc(h.get('last_error'))}</td><td>{_esc(h.get('updated_at'))}</td></tr>"
        )
    health_body = "\n".join(health_rows) or "<tr><td colspan='4'>No portal health data yet.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Job Agent Status</title>
  <style>
    :root {{ --bg:#0f1419; --card:#1a2332; --text:#e7ecf3; --muted:#8b9bb4; --accent:#3d9cf0; }}
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text);
           margin: 0; padding: 2rem; line-height: 1.45; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 .25rem; }}
    .sub {{ color: var(--muted); margin-bottom: 1.5rem; font-size: .9rem; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 2rem; }}
    .stat {{ background: var(--card); padding: .75rem 1rem; border-radius: 8px; min-width: 5rem; }}
    .stat .n {{ font-size: 1.4rem; font-weight: 700; }}
    .stat .l {{ color: var(--muted); font-size: .75rem; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; }}
    th, td {{ text-align: left; padding: .6rem .75rem; border-bottom: 1px solid #243044; font-size: .9rem; }}
    th {{ color: var(--muted); font-weight: 600; }}
    a {{ color: var(--accent); }}
    .badge {{ background: #243044; padding: .15rem .45rem; border-radius: 4px; font-size: .8rem; }}
    h2 {{ font-size: 1.1rem; margin: 2rem 0 .75rem; }}
  </style>
</head>
<body>
  <h1>Job Agent Status</h1>
  <p class="sub">Read-only report · generated {now}</p>
  <div class="stats">{funnel_html}</div>
  <h2>Recent applications</h2>
  <table>
    <thead><tr><th>Updated</th><th>Portal</th><th>Company</th><th>Title</th><th>Fit</th><th>Status</th></tr></thead>
    <tbody>{table_body}</tbody>
  </table>
  <h2>Portal health</h2>
  <table>
    <thead><tr><th>Portal</th><th>Auth</th><th>Last error</th><th>Updated</th></tr></thead>
    <tbody>{health_body}</tbody>
  </table>
</body>
</html>
"""


def main() -> int:
    out_dir = ROOT / "docs"
    out_dir.mkdir(exist_ok=True)
    tracker = Tracker(ROOT / "db" / "jobs.db")
    html_doc = render(tracker)
    (out_dir / "index.html").write_text(html_doc, encoding="utf-8")
    print(f"Wrote {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
