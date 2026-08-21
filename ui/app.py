"""Local-only Streamlit dashboard: start button, funnel, status edits."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from core.scheduler import Scheduler  # noqa: E402
from core.tracker import STATUSES, Tracker  # noqa: E402
from scripts.generate_report import render  # noqa: E402

CONFIG_PATH = ROOT / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


def main() -> None:
    st.set_page_config(page_title="Job Agent", layout="wide")
    st.title("Job Agent")

    cfg = load_config()
    tracker = Tracker(ROOT / "db" / "jobs.db")

    st.info(
        "France Travail: finds + scores jobs using your CV skills. "
        "Good fits go to **manual** queue — it does **not** upload/apply your resume yet. "
        "Open each JD link and apply yourself for now."
    )

    run_col, kill_col = st.columns([2, 1])
    with run_col:
        if st.button("▶  START SEARCH", type="primary", use_container_width=True):
            with st.spinner("Searching France Travail and scoring…"):
                cfg_run = load_config()
                cfg_run.setdefault("pacing", {})["daytime_only"] = False
                summary = Scheduler(cfg_run, root=ROOT).run_once()
                # Refresh static report
                html_doc = render(Tracker(ROOT / "db" / "jobs.db"))
                (ROOT / "docs").mkdir(exist_ok=True)
                (ROOT / "docs" / "index.html").write_text(html_doc, encoding="utf-8")
            st.success(
                f"Done — discovered {summary.get('discovered', 0)}, "
                f"manual {summary.get('manual', 0)}, "
                f"skipped {summary.get('skipped', 0)}, "
                f"errors {summary.get('errors') or 'none'}"
            )
            st.rerun()

    with kill_col:
        kill = st.toggle("Kill switch", value=bool(cfg.get("kill_switch")))
        if kill != bool(cfg.get("kill_switch")):
            cfg["kill_switch"] = kill
            save_config(cfg)
            st.success("Saved")

    st.subheader("Portals")
    portals = cfg.setdefault("portals", {})
    changed = False
    cols = st.columns(len(portals) or 1)
    for i, (name, pcfg) in enumerate(portals.items()):
        with cols[i % len(cols)]:
            en = st.checkbox(name, value=bool(pcfg.get("enabled")), key=f"p_{name}")
            if en != bool(pcfg.get("enabled")):
                pcfg["enabled"] = en
                changed = True
    if changed:
        save_config(cfg)
        st.rerun()

    st.subheader("Funnel")
    funnel = tracker.funnel_counts()
    if funnel:
        st.dataframe(
            [{"status": k, "count": v} for k, v in sorted(funnel.items())],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("No applications yet — press START SEARCH.")

    st.subheader("Applications")
    rows = tracker.applications_by_status()
    if not rows:
        st.write("Empty.")
        return

    for r in rows[:100]:
        with st.expander(
            f"[{r.get('status')}] {r.get('company')} — {r.get('title')} ({r.get('fit_score')})"
        ):
            st.write(f"Portal: `{r.get('portal')}` · {_loc(r)}")
            if r.get("error_message"):
                st.caption(r["error_message"])
            if r.get("url"):
                st.link_button("Open JD / apply manually", r["url"])
            new_status = st.selectbox(
                "Status",
                STATUSES,
                index=STATUSES.index(r["status"]) if r.get("status") in STATUSES else 0,
                key=f"st_{r['application_id']}",
            )
            if st.button("Save", key=f"save_{r['application_id']}"):
                tracker.update_status(int(r["application_id"]), new_status, note="manual UI edit")
                st.success("Updated")
                st.rerun()


def _loc(r: dict) -> str:
    return f"{r.get('location') or ''} · {r.get('remote_type') or ''}"


if __name__ == "__main__":
    main()
