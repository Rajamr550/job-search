"""Offline demo connector — fake French roles so you can test without API keys."""

from __future__ import annotations

from connectors.base import ApplyResult, Connector, JobPosting, RemoteType


SAMPLE_JOBS = [] 

# SAMPLE_JOBS = [
#     JobPosting(
#         portal="demo",
#         external_id="demo-1",
#         title="Senior Java / Spring Boot Engineer",
#         company="Acme Cloud FR",
#         location="Paris (télétravail possible)",
#         url="https://example.com/jobs/demo-1",
#         description=(
#             "We need a senior Java engineer with Spring Boot, microservices, Docker, "
#             "Kubernetes, AWS, and CI/CD. Hybrid télétravail 3 days/week. React is a plus."
#         ),
#         remote_type=RemoteType.HYBRID,
#     ),
#     JobPosting(
#         portal="demo",
#         external_id="demo-2",
#         title="Fullstack React / Java Developer",
#         company="Startup Remote FR",
#         location="Full remote France",
#         url="https://example.com/jobs/demo-2",
#         description=(
#             "Fully remote fullstack role: React, TypeScript, Java, Spring Boot, PostgreSQL, "
#             "Kafka. Must have EU citizenship — no visa sponsorship."
#         ),
#         remote_type=RemoteType.REMOTE,
#     ),
#     JobPosting(
#         portal="demo",
#         external_id="demo-3",
#         title="Junior PHP Developer",
#         company="Legacy Corp",
#         location="Lyon présentiel",
#         url="https://example.com/jobs/demo-3",
#         description="Looking for a junior PHP / WordPress developer. Onsite only in Lyon.",
#         remote_type=RemoteType.ONSITE,
#     ),
# ]


class DemoConnector(Connector):
    name = "demo"

    def search_jobs(self, keywords: list[str], location: str, limit: int = 20) -> list[JobPosting]:
        return SAMPLE_JOBS[:limit]

    def apply(self, job: JobPosting, resume_path: str) -> ApplyResult:
        return ApplyResult(success=True, message="demo apply OK")
