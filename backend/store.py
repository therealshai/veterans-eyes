"""Guides on disk. One folder per guide:

    data/guides/<id>/
        video.mp4      the expert's recording
        job.json       status while processing: {"status", "progress", "error", "title", "domain"}
        raw_1.json     Wonder's raw answer (kept so a bad parse never costs a second call)
        guide.json     the validated guide (+ keyframes once built)
        step_3.jpg     highlighted keyframe per step

Files instead of a database: enough for a demo, easy to inspect, nothing to set up.
"""
import json
import re
import shutil
import uuid
from pathlib import Path

from backend.config import DEMO_DIR, GUIDES_DIR
from backend.models import Guide, GuideSummary

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def new_id(hint: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", hint.lower()).strip("-")[:40]
    return f"{base}-{uuid.uuid4().hex[:6]}" if base else uuid.uuid4().hex[:10]


def folder(guide_id: str) -> Path:
    """The guide's folder. Refuses ids like '../../etc' (path traversal)."""
    if not _SAFE_ID.match(guide_id):
        raise ValueError(f"Bad guide id: {guide_id!r}")
    return GUIDES_DIR / guide_id


def file_path(guide_id: str, name: str) -> Path:
    if not re.match(r"^[A-Za-z0-9_.-]{1,80}$", name) or ".." in name:
        raise ValueError(f"Bad file name: {name!r}")
    return folder(guide_id) / name


def save_guide(guide: Guide) -> None:
    d = folder(guide.id)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "guide.json.tmp"
    tmp.write_text(guide.model_dump_json(indent=2))
    tmp.replace(d / "guide.json")          # atomic: readers never see half a file


def load_guide(guide_id: str) -> Guide | None:
    p = folder(guide_id) / "guide.json"
    return Guide.model_validate_json(p.read_text()) if p.exists() else None


def write_job(guide_id: str, **fields) -> None:
    d = folder(guide_id)
    d.mkdir(parents=True, exist_ok=True)
    job = read_job(guide_id)
    job.update(fields)
    (d / "job.json").write_text(json.dumps(job, indent=2))


def read_job(guide_id: str) -> dict:
    p = folder(guide_id) / "job.json"
    return json.loads(p.read_text()) if p.exists() else {}


def summary(guide_id: str) -> GuideSummary | None:
    guide, job = load_guide(guide_id), read_job(guide_id)
    if guide is None and not job:
        return None
    status = job.get("status") if job.get("status") in ("processing", "failed") else (guide.status if guide else "failed")
    if guide is None:
        return GuideSummary(id=guide_id, title=job.get("title") or guide_id, domain=job.get("domain", ""),
                            status=status, progress=job.get("progress", ""), steps=0, critical_steps=0, duration_s=0)
    cover = next((s.keyframe for s in guide.steps if s.keyframe), None)
    return GuideSummary(id=guide.id, title=guide.title, domain=guide.domain, status=status,
                        progress=job.get("progress", "") if status == "processing" else "",
                        steps=len(guide.steps), critical_steps=sum(s.critical for s in guide.steps),
                        duration_s=guide.duration_s, cover=cover)


def list_guides() -> list[GuideSummary]:
    if not GUIDES_DIR.exists():
        return []
    items = [summary(p.name) for p in sorted(GUIDES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
             if p.is_dir() and _SAFE_ID.match(p.name)]
    return [s for s in items if s]


def seed_demo_guides() -> list[str]:
    """Copy the sample guides in demo/ into data/guides/ if they aren't there yet,
    so a fresh clone (or a judge) opens the app to something ready to coach."""
    seeded = []
    if not DEMO_DIR.is_dir():
        return seeded
    for src in sorted(DEMO_DIR.iterdir()):
        if src.is_dir() and (src / "guide.json").exists() and _SAFE_ID.match(src.name):
            dst = GUIDES_DIR / src.name
            if not dst.exists():
                shutil.copytree(src, dst)
                seeded.append(src.name)
    return seeded
