"""Checks every REAL guide you have built in data/guides/ (skips until one exists).
The other test files use fake data; this one tells you if Wonder's real output holds up."""
import pytest

from backend.config import GUIDES_DIR
from backend.models import Guide

REAL = sorted(GUIDES_DIR.glob("*/guide.json"))


@pytest.mark.skipif(not REAL, reason="no real guide yet: run extract_guide first")
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.parent.name)
def test_real_guide_is_usable(path):
    g = Guide.model_validate_json(path.read_text())
    assert any(s.critical for s in g.steps), "no critical step: the coach would never run a check"
    assert all(s.parts and s.check_hint.strip() for s in g.steps)
