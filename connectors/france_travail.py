"""France Travail (Pôle Emploi) connector — official search API."""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from connectors.base import ApplyResult, Connector, JobPosting, RemoteType

log = logging.getLogger(__name__)

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# FT motsCles is picky: too many English tokens → 204. Prefer short FR/EN job phrases.
DEFAULT_QUERIES = [
    "développeur Java",
    "ingénieur Java",
    "Spring Boot",
    "développeur fullstack",
]


class FranceTravailConnector(Connector):
    name = "france_travail"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")
        self._token: Optional[str] = None

    def is_authenticated(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        if self._token:
            return self._token
        if not self.is_authenticated():
            raise RuntimeError(
                "France Travail credentials missing. Set FRANCE_TRAVAIL_CLIENT_ID/SECRET."
            )
        resp = requests.post(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _search_once(self, query: str, limit: int) -> list[JobPosting]:
        headers = {"Authorization": f"Bearer {self._get_token()}", "Accept": "application/json"}
        params = {
            "motsCles": query,
            "range": f"0-{max(0, limit - 1)}",
            "sort": 1,
        }
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=45)
        if resp.status_code == 204:
            log.info("france_travail: 204 no content for query=%r", query)
            return []
        if resp.status_code == 401:
            log.error(
                "france_travail: 401 unauthorized — wrong secret or missing "
                "Offres d'emploi v2 subscription"
            )
            return []
        resp.raise_for_status()
        data = resp.json()
        results: list[JobPosting] = []
        for item in data.get("resultats", []):
            lieu = item.get("lieuTravail") or {}
            loc_label = lieu.get("libelle") or ""
            desc = item.get("description") or ""
            remote = _infer_remote(desc, loc_label, item)
            results.append(
                JobPosting(
                    portal=self.name,
                    external_id=str(item.get("id") or ""),
                    title=item.get("intitule") or "",
                    company=(item.get("entreprise") or {}).get("nom") or "Unknown",
                    location=loc_label,
                    url=item.get("origineOffre", {}).get("urlOrigine")
                    or f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}",
                    description=desc,
                    remote_type=remote,
                    raw=item,
                )
            )
        log.info("france_travail: %s offers for %r", len(results), query)
        return results

    def search_jobs(self, keywords: list[str], location: str, limit: int = 20) -> list[JobPosting]:
        if not self.is_authenticated():
            log.warning(
                "france_travail: no credentials — create job-agent/.env with "
                "FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET"
            )
            return []

        try:
            self._get_token()
        except Exception as exc:  # noqa: BLE001
            log.error(
                "france_travail: token failed (%s). "
                "Subscribe your app to API « Offres d'emploi v2 ».",
                exc,
            )
            return []

        # Prefer short phrases. Joining all skills (Java Spring React…) usually returns 204.
        queries = _build_queries(keywords)
        per_query = max(5, limit // max(len(queries), 1))
        seen: set[str] = set()
        out: list[JobPosting] = []
        try:
            for q in queries:
                if len(out) >= limit:
                    break
                for job in self._search_once(q, per_query):
                    if job.external_id in seen:
                        continue
                    seen.add(job.external_id)
                    out.append(job)
                    if len(out) >= limit:
                        break
        except requests.RequestException as exc:
            log.error("france_travail search failed: %s", exc)
            return out

        log.info("france_travail: %s unique offers total", len(out))
        return out

    def apply(self, job: JobPosting, resume_path: str) -> ApplyResult:
        return ApplyResult(
            success=False,
            message="Queued for manual apply (France Travail native apply is Phase 2)",
            needs_manual=True,
        )


def _build_queries(keywords: list[str]) -> list[str]:
    """Build short FT-friendly queries from config keywords + French defaults."""
    queries: list[str] = []
    for kw in keywords:
        k = (kw or "").strip()
        if not k:
            continue
        low = k.lower()
        if low == "java":
            queries.append("développeur Java")
        elif low in {"spring boot", "react", "angular", "kubernetes", "docker", "aws"}:
            queries.append(k)
        if len(queries) >= 4:
            break
    if not queries:
        queries = list(DEFAULT_QUERIES)
    if "développeur Java" not in queries:
        queries.insert(0, "développeur Java")
    seen: set[str] = set()
    uniq: list[str] = []
    for q in queries:
        if q.lower() not in seen:
            seen.add(q.lower())
            uniq.append(q)
    return uniq[:5]


def _infer_remote(desc: str, location: str, item: dict) -> RemoteType:
    blob = f"{desc} {location}".lower()
    if "télétravail" in blob or "teletravail" in blob or "remote" in blob:
        if "hybride" in blob or "hybrid" in blob:
            return RemoteType.HYBRID
        return RemoteType.REMOTE
    complements = item.get("complementLieu") or ""
    if "télétravail" in str(complements).lower():
        return RemoteType.REMOTE
    return RemoteType.UNKNOWN
