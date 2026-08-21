"""Extract skills/keywords from a CV (markdown or PDF)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PLACEHOLDER_PATTERNS = [
    r"\[your-[^\]]+\]",
    r"\[TODO[^\]]*\]",
    r"YYYY|MM/DD|TBD",
    r"lorem ipsum",
]

SECTION_HEADERS = re.compile(
    r"(?im)^(#{1,3}\s*)?(skills|experience keywords|experience|compétences|technologies)\s*$"
)


@dataclass
class CVProfile:
    skills: list[str] = field(default_factory=list)
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)
    source_path: str = ""


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_md_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _skills_sections(text: str) -> str:
    """Prefer content under Skills / Experience keywords headings when present."""
    lines = text.splitlines()
    chunks: list[str] = []
    capture = False
    for line in lines:
        if SECTION_HEADERS.match(line.strip()):
            capture = True
            continue
        if capture and re.match(r"^#{1,3}\s+\S", line):
            capture = False
            continue
        if capture:
            chunks.append(line)
    return "\n".join(chunks) if chunks else text


def _tokenize(text: str) -> list[str]:
    text = _skills_sections(text)
    chunks = re.split(r"[,;\n•|]+", text)
    skills: list[str] = []
    seen: set[str] = set()
    skip = {
        "skills",
        "experience keywords",
        "experience",
        "education",
        "cv profile",
        "compétences",
        "technologies",
    }
    for chunk in chunks:
        s = re.sub(r"^[#*\-\d.\s]+", "", chunk).strip()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"\(.*?\)", "", s).strip()
        if len(s) < 2 or len(s) > 50:
            continue
        if s.lower() in skip or "edit this" in s.lower() or "config.yaml" in s.lower():
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            skills.append(s)
    return skills


def _find_placeholders(text: str) -> list[str]:
    found = []
    for pat in PLACEHOLDER_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            found.append(m.group(0))
    return found


def parse_cv(path: str | Path) -> CVProfile:
    path = Path(path)
    if not path.exists():
        return CVProfile(warnings=[f"CV not found: {path}"], source_path=str(path))

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = _extract_pdf_text(path)
    elif suffix in {".md", ".txt", ".markdown"}:
        raw = _extract_md_text(path)
    else:
        return CVProfile(warnings=[f"Unsupported CV format: {suffix}"], source_path=str(path))

    warnings = []
    placeholders = _find_placeholders(raw)
    if placeholders:
        warnings.append(f"Placeholder text found: {', '.join(placeholders[:5])}")

    skills = _tokenize(raw)
    if len(skills) < 5:
        warnings.append("Few skills extracted — check CV content or format.")

    return CVProfile(skills=skills, raw_text=raw, warnings=warnings, source_path=str(path))
