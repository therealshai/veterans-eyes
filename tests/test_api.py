import json

import pytest
from fastapi.testclient import TestClient

from backend import meta, store
from backend.app import app
from backend.expert import pipeline
from backend.live import asr_relay
from backend.models import Box, Guide
from tests.conftest import guide_dict, step

client = TestClient(app)


def test_list_and_get(saved_guide):
    assert [g["id"] for g in client.get("/api/guides").json()] == ["demo"]
    body = client.get("/api/guides/demo").json()
    assert body["guide"]["title"] == "Remove the wheel"


def test_bad_ids_and_paths_are_refused(saved_guide):
    assert client.get("/api/guides/..%2F..%2Fetc").status_code in (400, 404)
    assert client.get("/api/guides/demo/files/guide.json").status_code == 404
    assert client.get("/api/guides/demo/files/..%2F.env").status_code in (400, 404)


def test_ask(saved_guide, monkeypatch):
    seen = {}

    def fake_spark(parts, **kw):
        seen["parts"] = parts
        return "Turn it anticlockwise."

    monkeypatch.setattr(meta, "spark", fake_spark)
    r = client.post("/api/coach/ask", data={"guide_id": "demo", "step_no": 2, "question": "Which way?"},
                    files={"frame": ("f.jpg", b"\xff\xd8fakejpeg", "image/jpeg")})
    assert r.status_code == 200 and r.json()["answer"] == "Turn it anticlockwise."
    assert "Which way?" in seen["parts"][0]["text"] and seen["parts"][1]["type"] == "input_image"


def test_ask_retries_an_empty_reply(saved_guide, monkeypatch):
    replies = iter(["", "Turn it anticlockwise."])
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: next(replies))
    r = client.post("/api/coach/ask", data={"guide_id": "demo", "step_no": 2, "question": "Which way?"})
    assert r.json()["answer"] == "Turn it anticlockwise."


def test_ask_falls_back_when_both_replies_are_empty(saved_guide, monkeypatch):
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: "  ")
    r = client.post("/api/coach/ask", data={"guide_id": "demo", "step_no": 2, "question": "Which way?"})
    assert r.json()["answer"] == "Sorry, I didn't catch that. Ask again?"


def test_truncated_verdict_becomes_unclear_not_a_crash(monkeypatch):
    from backend.live import coach as coach_mod
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: '{"verdict": "ma')
    assert coach_mod.judge("step", None, b"frame")["verdict"] == "unclear"
    def boom(parts, **kw):
        raise RuntimeError("reply incomplete after retry")
    monkeypatch.setattr(meta, "spark", boom)
    assert coach_mod.judge("step", None, b"frame")["verdict"] == "unclear"


def test_check_runs_verdict_and_highlight(saved_guide, monkeypatch):
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: json.dumps({"verdict": "fix", "say": "Wrong bolt."}))
    monkeypatch.setattr(meta, "sam_boxes", lambda jpeg, c: [Box(x1=1, y1=2, x2=3, y2=4, w=10, h=10)])
    r = client.post("/api/coach/check", data={"guide_id": "demo", "step_no": 2},
                    files={"frame": ("f.jpg", b"\xff\xd8fake", "image/jpeg")})
    body = r.json()
    assert body["verdict"] == "fix" and body["highlight"]["x2"] == 3


def test_edit_and_publish(saved_guide):
    g = client.get("/api/guides/demo").json()["guide"]
    g["steps"][0]["instruction"] = "Loosen the bolt"
    assert client.put("/api/guides/demo", json=g).status_code == 200
    g["steps"][0]["end_s"] = -1                                    # invalid edit is refused
    assert client.put("/api/guides/demo", json=g).status_code == 422
    assert client.post("/api/guides/demo/publish").json()["status"] == "published"
    assert store.load_guide("demo").steps[0].instruction == "Loosen the bolt"


def test_upload_starts_background_job(monkeypatch):
    started = []
    monkeypatch.setattr(pipeline, "run", lambda gid, model, domain: started.append(gid))
    r = client.post("/api/guides", data={"title": "Air filter"},
                    files={"video": ("air.mp4", b"0" * 1000, "video/mp4")})
    assert r.status_code == 202 and r.json()["status"] == "processing"
    assert started == [r.json()["id"]] and r.json()["id"].startswith("air-filter-")


def test_voice_relay_protocol(monkeypatch):
    async def fake_stream(audio, to_phone):
        got = b""
        while (chunk := await audio.get()) is not None:
            got += chunk
        await to_phone({"type": "final", "text": f"{len(got)} bytes"})

    monkeypatch.setattr(asr_relay, "_meta_stream", fake_stream)
    with client.websocket_connect("/ws/asr") as ws:
        ws.send_text(json.dumps({"type": "start"}))
        ws.send_bytes(b"\x00" * 3840)
        ws.send_bytes(b"\x00" * 3840)
        ws.send_text(json.dumps({"type": "stop"}))
        assert json.loads(ws.receive_text()) == {"type": "final", "text": "7680 bytes"}


def test_guide_without_critical_steps(tmp_guides):
    guide = Guide.model_validate({**guide_dict(), "id": "plain",
                                  "steps": [step(1, 0.0, 3.0), step(2, 3.0, 6.0)]})
    store.save_guide(guide)
    assert client.get("/api/guides/plain").json()["guide"]["title"] == "Remove the wheel"
    card = next(g for g in client.get("/api/guides").json() if g["id"] == "plain")
    assert (card["steps"], card["critical_steps"]) == (2, 0)


def test_guide_where_every_step_needs_review(tmp_guides, monkeypatch):
    guide = Guide.model_validate({
        **guide_dict(), "id": "review-me",
        "steps": [step(1, 0.0, 3.0, needs_review=True), step(2, 3.0, 6.0, needs_review=True)]})
    store.save_guide(guide)
    assert client.get("/api/guides/review-me").status_code == 200
    card = next(g for g in client.get("/api/guides").json() if g["id"] == "review-me")
    assert card["cover"] is None                       # no keyframe found anywhere yet
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: json.dumps({"verdict": "match", "say": "ok"}))
    monkeypatch.setattr(meta, "sam_boxes", lambda jpeg, c: [])
    r = client.post("/api/coach/check", data={"guide_id": "review-me", "step_no": 1},
                    files={"frame": ("f.jpg", b"\xff\xd8fake", "image/jpeg")})
    assert r.status_code == 200 and r.json()["highlight"] is None   # works with no expert image


@pytest.mark.parametrize("bad_id", ["..", "%2e", "%2e%2e", "%2e%2e%2fsecret", "%2Fetc%2Fpasswd",
                                    "a%2Fb", "a%20b", "x.json"])
def test_evil_guide_ids_are_refused(saved_guide, bad_id):
    assert client.get(f"/api/guides/{bad_id}").status_code in (400, 404)


@pytest.mark.parametrize("name", ["guide.json", "job.json", "raw_1.json", "..%2Fvideo.mp4",
                                  "%2e%2e%2fvideo.mp4", "%2Fetc%2Fpasswd", "a%2Fb.jpg"])
def test_evil_file_names_are_refused(saved_guide, name):
    assert client.get(f"/api/guides/demo/files/{name}").status_code in (400, 404)


def test_real_files_still_served(saved_guide):
    r = client.get("/api/guides/demo/files/video.mp4")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"


def test_store_refuses_bad_paths():
    for bad in ["../x", "..", ".", "/abs/path", "a/b", "", "a b", "x" * 81]:
        with pytest.raises(ValueError):
            store.folder(bad)
    for bad in ["../x", "..", "/abs", "a/b", "x" * 81]:
        with pytest.raises(ValueError):
            store.file_path("demo", bad)
