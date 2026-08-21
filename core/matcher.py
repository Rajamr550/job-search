"""Score JDs against CV profile: keywords + remote preference + dealbreakers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from connectors.base import JobPosting, RemoteType
from core.cv_parser import CVProfile


@dataclass
class MatchResult:
    score: float
    keyword_score: float
    location_score: float
    matched_skills: list[str]
    dealbreaker: bool
    dealbreaker_reason: str = ""
    should_apply: bool = False


def _detect_remote_type(text: str, location: str) -> RemoteType:
    blob = f"{text} {location}".lower()
    if re.search(r"\bfull[\s-]?remote\b|\btélétravail\s*(100|complet|total)\b|\bfully remote\b|\bremote[\s-]?first\b", blob):
        return RemoteType.REMOTE
    if re.search(r"\bhybrid\b|\bhybride\b|\btélétravail\b|\bremote\b", blob):
        # Prefer remote if explicit; hybrid otherwise
        if "remote" in blob and "hybrid" not in blob and "hybride" not in blob:
            return RemoteType.REMOTE
        if "hybrid" in blob or "hybride" in blob:
            return RemoteType.HYBRID
        return RemoteType.REMOTE
    if re.search(r"\bonsite\b|\bon[\s-]?site\b|\bsur site\b|\bpresentiel\b|\bprésentiel\b", blob):
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _keyword_overlap(skills: list[str], jd: str) -> tuple[float, list[str]]:
    if not skills or not jd:
        return 0.0, []
    jd_lower = jd.lower()
    matched: list[str] = []
    for skill in skills:
        s = skill.lower()
        if len(s) < 2:
            continue
        if s in jd_lower or fuzz.partial_ratio(s, jd_lower) >= 88:
            matched.append(skill)
    # Points per hit (diminishing): ~6 strong hits ≈ 70+, 9+ ≈ 90+
    n = len(matched)
    if n == 0:
        score = 0.0
    else:
        score = min(100.0, 15 + n * 9)
    return score, matched


def _has_dealbreaker(jd: str, patterns: list[str]) -> tuple[bool, str]:
    low = jd.lower()
    for pat in patterns:
        if pat.lower() in low:
            return True, pat
    # Common French/English visa blockers
    extra = [
        r"citoyenneté\s+européenne",
        r"nationalité\s+européenne",
        r"no\s+sponsorship",
        r"must\s+have\s+(eu|european)\s+(citizenship|passport)",
    ]
    for pat in extra:
        if re.search(pat, low):
            return True, pat
    return False, ""


def score_job(
    job: JobPosting,
    profile: CVProfile,
    *,
    threshold: float = 65,
    location_weights: dict | None = None,
    dealbreakers: list[str] | None = None,
) -> MatchResult:
    location_weights = location_weights or {
        "remote": 1.0,
        "hybrid": 0.85,
        "onsite": 0.7,
        "unknown": 0.75,
    }
    dealbreakers = dealbreakers or []

    jd = f"{job.title}\n{job.company}\n{job.location}\n{job.description}"
    blocked, reason = _has_dealbreaker(jd, dealbreakers)
    if blocked:
        return MatchResult(
            score=0,
            keyword_score=0,
            location_score=0,
            matched_skills=[],
            dealbreaker=True,
            dealbreaker_reason=reason,
            should_apply=False,
        )

    kw_score, matched = _keyword_overlap(profile.skills, jd)

    remote = job.remote_type
    if remote == RemoteType.UNKNOWN:
        remote = _detect_remote_type(job.description or "", job.location or "")
        job.remote_type = remote

    loc_w = float(location_weights.get(remote.value, location_weights.get("unknown", 0.75)))
    # Blend: 75% keywords, 25% location preference (as score contribution)
    final = (kw_score * 0.75) + (loc_w * 100 * 0.25)
    final = round(min(100.0, final), 1)

    return MatchResult(
        score=final,
        keyword_score=round(kw_score, 1),
        location_score=round(loc_w * 100, 1),
        matched_skills=matched,
        dealbreaker=False,
        should_apply=final >= threshold,
    )
