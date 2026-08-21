"""Orchestration: discover → match → apply/queue, with caps and pacing."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from connectors.apec import ApecConnector
from connectors.base import Connector
from connectors.demo import DemoConnector
from connectors.france_travail import FranceTravailConnector
from connectors.indeed import IndeedConnector
from connectors.linkedin import LinkedInConnector
from connectors.welcome_jungle import WelcomeJungleConnector
from core.cv_parser import CVProfile, parse_cv
from core.matcher import score_job
from core.tracker import Tracker

log = logging.getLogger(__name__)

CONNECTOR_MAP: dict[str, type[Connector]] = {
    "demo": DemoConnector,
    "france_travail": FranceTravailConnector,
    "linkedin": LinkedInConnector,
    "indeed": IndeedConnector,
    "welcome_jungle": WelcomeJungleConnector,
    "apec": ApecConnector,
}


class Scheduler:
    def __init__(self, config: dict[str, Any], tracker: Tracker | None = None, root: Path | None = None):
        self.config = config
        self.root = root or Path.cwd()
        self.tracker = tracker or Tracker(self.root / "db" / "jobs.db")
        self.profile: CVProfile | None = None
        self._hourly_counts: dict[str, int] = {}
        self._daily_counts: dict[str, int] = {}

    def _load_profile(self) -> CVProfile:
        cv_path = self.root / self.config.get("cv_path", "resume/cv_profile.md")
        profile = parse_cv(cv_path)
        for w in profile.warnings:
            log.warning("CV: %s", w)
        self.profile = profile
        return profile

    def _within_daytime(self) -> bool:
        pacing = self.config.get("pacing") or {}
        if not pacing.get("daytime_only", True):
            return True
        tz = ZoneInfo(pacing.get("timezone", "Europe/Paris"))
        now = datetime.now(tz)
        return pacing.get("day_start_hour", 9) <= now.hour < pacing.get("day_end_hour", 18)

    def _sleep(self) -> None:
        pacing = self.config.get("pacing") or {}
        lo = float(pacing.get("min_delay_seconds", 3))
        hi = float(pacing.get("max_delay_seconds", 12))
        delay = random.uniform(lo, hi)
        log.debug("pacing sleep %.1fs", delay)
        time.sleep(delay)

    def _build_connectors(self) -> list[tuple[str, Connector, dict]]:
        portals = self.config.get("portals") or {}
        out: list[tuple[str, Connector, dict]] = []
        for name, cls in CONNECTOR_MAP.items():
            cfg = portals.get(name) or {}
            if not cfg.get("enabled", False):
                continue
            out.append((name, cls(), cfg))
        return out

    def _under_caps(self, portal: str, cfg: dict) -> bool:
        daily = self._daily_counts.get(portal, 0)
        hourly = self._hourly_counts.get(portal, 0)
        if daily >= int(cfg.get("daily_cap", 10)):
            log.info("%s: daily cap reached (%s)", portal, daily)
            return False
        if hourly >= int(cfg.get("hourly_cap", 5)):
            log.info("%s: hourly cap reached (%s)", portal, hourly)
            return False
        return True

    def _bump_caps(self, portal: str) -> None:
        self._daily_counts[portal] = self._daily_counts.get(portal, 0) + 1
        self._hourly_counts[portal] = self._hourly_counts.get(portal, 0) + 1

    def run_once(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "discovered": 0,
            "queued_apply": 0,
            "applied": 0,
            "skipped": 0,
            "manual": 0,
            "errors": [],
        }

        if self.config.get("kill_switch"):
            log.warning("Kill switch ON — aborting run")
            summary["errors"].append("kill_switch")
            return summary

        if not self._within_daytime():
            log.info("Outside daytime window — skipping (set pacing.daytime_only: false to override)")
            summary["errors"].append("outside_daytime")
            return summary

        profile = self._load_profile()
        search = self.config.get("search") or {}
        matching = self.config.get("matching") or {}
        keywords = search.get("keywords") or []
        location = search.get("location") or "France"
        threshold = float(matching.get("threshold", 65))
        loc_weights = matching.get("location_weights") or {}
        dealbreakers = matching.get("dealbreakers") or []
        resume_path = str(self.root / self.config.get("cv_path", "resume/cv_profile.md"))

        for portal_name, connector, cfg in self._build_connectors():
            if not self._under_caps(portal_name, cfg):
                continue
            try:
                jobs = connector.search_jobs(keywords, location, limit=int(cfg.get("daily_cap", 15)))
            except Exception as exc:  # noqa: BLE001
                log.exception("%s search failed", portal_name)
                summary["errors"].append(f"{portal_name}: {exc}")
                self.tracker.set_portal_health(portal_name, needs_reauth=True, last_error=str(exc))
                continue

            self.tracker.set_portal_health(portal_name, needs_reauth=False, last_error="")
            for job in jobs:
                if not self._under_caps(portal_name, cfg):
                    break
                if not job.description:
                    try:
                        job.description = connector.get_job_description(job)
                    except Exception:  # noqa: BLE001
                        pass

                result = score_job(
                    job,
                    profile,
                    threshold=threshold,
                    location_weights=loc_weights,
                    dealbreakers=dealbreakers,
                )
                job_id = self.tracker.upsert_job(
                    portal=job.portal,
                    external_id=job.external_id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    remote_type=job.remote_type.value,
                    url=job.url,
                    description=job.description[:8000],
                    fit_score=result.score,
                )
                summary["discovered"] += 1

                if self.tracker.has_application(job_id):
                    continue

                if result.dealbreaker or not result.should_apply:
                    reason = result.dealbreaker_reason or f"low fit ({result.score})"
                    self.tracker.create_application(job_id, status="skipped", error_message=reason)
                    summary["skipped"] += 1
                    continue

                app_id = self.tracker.create_application(
                    job_id, status="queued", resume_version=Path(resume_path).name
                )
                summary["queued_apply"] += 1
                self._sleep()

                apply_result = connector.apply(job, resume_path)
                self._bump_caps(portal_name)

                if apply_result.needs_reauth:
                    self.tracker.set_portal_health(
                        portal_name, needs_reauth=True, last_error=apply_result.message
                    )
                    self.tracker.update_status(app_id, "failed", apply_result.message)
                    summary["errors"].append(f"{portal_name}: needs re-auth")
                    break

                if apply_result.needs_manual:
                    self.tracker.update_status(app_id, "manual", apply_result.message)
                    summary["manual"] += 1
                elif apply_result.success:
                    self.tracker.update_status(app_id, "applied", apply_result.message)
                    summary["applied"] += 1
                else:
                    self.tracker.update_status(app_id, "failed", apply_result.message)

        log.info("Run summary: %s", summary)
        return summary
