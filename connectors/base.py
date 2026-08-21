"""Shared types and base connector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


@dataclass
class JobPosting:
    portal: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    remote_type: RemoteType = RemoteType.UNKNOWN
    raw: dict = field(default_factory=dict)


@dataclass
class ApplyResult:
    success: bool
    message: str = ""
    needs_manual: bool = False
    needs_reauth: bool = False


class Connector(ABC):
    """Common portal interface: search → describe → apply → status."""

    name: str = "base"

    @abstractmethod
    def search_jobs(self, keywords: list[str], location: str, limit: int = 20) -> list[JobPosting]:
        ...

    def get_job_description(self, job: JobPosting) -> str:
        """Fetch full JD if search only returned a snippet. Default: use existing."""
        return job.description

    def apply(self, job: JobPosting, resume_path: str) -> ApplyResult:
        """Attempt native apply. Override in real connectors."""
        return ApplyResult(success=False, message="apply not implemented", needs_manual=True)

    def check_status(self, external_id: str) -> Optional[str]:
        return None

    def is_authenticated(self) -> bool:
        return True
