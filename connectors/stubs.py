"""Stub Playwright connectors — search/apply wired later; session-aware shell for now."""

from __future__ import annotations

import logging
from pathlib import Path

from connectors.base import ApplyResult, Connector, JobPosting

log = logging.getLogger(__name__)

AUTH_DIR = Path(".auth")


class SessionConnector(Connector):
    """Base for portals that need a saved Playwright storage_state."""

    login_url: str = ""

    def __init__(self):
        self.auth_file = AUTH_DIR / f"{self.name}.json"

    def is_authenticated(self) -> bool:
        return self.auth_file.exists()

    def search_jobs(self, keywords: list[str], location: str, limit: int = 20) -> list[JobPosting]:
        if not self.is_authenticated():
            log.warning("%s: no session at %s — run scripts/login_bootstrap.py", self.name, self.auth_file)
            return []
        log.info("%s: Playwright search not implemented yet (stub). Keywords=%s", self.name, keywords[:3])
        return []

    def apply(self, job: JobPosting, resume_path: str) -> ApplyResult:
        return ApplyResult(
            success=False,
            message=f"{self.name} apply not implemented yet",
            needs_manual=True,
            needs_reauth=not self.is_authenticated(),
        )


class LinkedInConnector(SessionConnector):
    name = "linkedin"
    login_url = "https://www.linkedin.com/login"


class IndeedConnector(SessionConnector):
    name = "indeed"
    login_url = "https://secure.indeed.com/auth"


class WelcomeJungleConnector(SessionConnector):
    name = "welcome_jungle"
    login_url = "https://www.welcometothejungle.com/en/login"


class ApecConnector(SessionConnector):
    name = "apec"
    login_url = "https://www.apec.fr/"
