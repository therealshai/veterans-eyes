"""Shared test setup. Every test gets an empty temporary data folder, and no
test ever reaches Meta's API: model calls are replaced with fakes."""
import os
os.environ.setdefault("VE_FAKE", "0")   # tests use their own fakes, never demo mode

import subprocess

import pytest

from backend import store
from backend.models import Guide


@pytest.fixture(autouse=True)
def tmp_guides(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "GUIDES_DIR", tmp_path / "guides")
    return tmp_path / "guides"


def step(n, start, end, **kw):
    base = dict(step_no=n, start_s=start, end_s=end, instruction=f"Do step {n}", parts=["bolt"],
                tools=[], expert_tips=[], warnings=[], critical=False, check_hint="bolt is tight")
    base.update(kw)
    return base


def guide_dict(**kw):
    base = dict(title="Remove the wheel", domain="bike", source_video="clip.mp4", duration_s=6.0,
                steps=[step(1, 0.0, 3.0), step(2, 3.0, 6.0, critical=True, parts=["axle nut"])])
    base.update(kw)
    return base


@pytest.fixture
def saved_guide(tmp_guides):
    """A guide on disk with a short generated test video, like after extract_guide."""
    guide = Guide.model_validate({**guide_dict(), "id": "demo"})
    d = tmp_guides / "demo"
    d.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                    "-t", "6", "-pix_fmt", "yuv420p", str(d / "video.mp4")], check=True)
    store.save_guide(guide)
    return guide
