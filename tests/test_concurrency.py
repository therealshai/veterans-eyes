"""Live calls must overlap: five slow checks at once take ~1 s, not ~5 s."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend import meta
from backend.app import app
from backend.models import Box

client = TestClient(app)


def test_five_checks_overlap(saved_guide, monkeypatch):
    def slow_spark(parts, **kw):
        time.sleep(1)
        return json.dumps({"verdict": "match", "say": "Looks right."})

    def slow_sam(jpeg, concept):
        time.sleep(1)
        return [Box(x1=1, y1=1, x2=2, y2=2, w=9, h=9)]

    monkeypatch.setattr(meta, "spark", slow_spark)
    monkeypatch.setattr(meta, "sam_boxes", slow_sam)

    def one(_):
        r = client.post("/api/coach/check", data={"guide_id": "demo", "step_no": 2},
                        files={"frame": ("f.jpg", b"\xff\xd8fake", "image/jpeg")})
        assert r.status_code == 200
        return r.json()["verdict"]

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:
        assert list(pool.map(one, range(5))) == ["match"] * 5
    assert time.perf_counter() - t0 < 4.0, "checks ran one after another instead of together"
