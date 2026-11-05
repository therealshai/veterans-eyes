import json

from backend import meta, store
from backend.expert import keyframes
from backend.expert.keyframes import FrameFinding, pick_keyframe
from backend.models import Box


def B(x1, y1, x2, y2, score=None):
    return Box(x1=x1, y1=y1, x2=x2, y2=y2, w=320, h=240, score=score)


def f(hands, parts):
    return FrameFinding(t=0, jpeg=b"", hands=hands, parts=parts)


def test_rule1_contact_wins():
    frames = [f([], [B(0, 0, 10, 10, 0.99)]),                       # part, no hand
              f([B(0, 0, 100, 100)], [B(50, 50, 60, 60, 0.5)])]     # hand on part
    pick = pick_keyframe(frames)
    assert (pick.index, pick.reason) == (1, "contact")


def test_rule2_most_confident_part():
    frames = [f([], [B(0, 0, 10, 10, 0.4)]), f([], [B(0, 0, 10, 10, 0.9)])]
    assert (pick_keyframe(frames).index, pick_keyframe(frames).reason) == (1, "part")


def test_rule3_nothing_found_takes_middle():
    pick = pick_keyframe([f([], []), f([], []), f([], [])])
    assert (pick.index, pick.box, pick.reason) == (1, None, "none")


def test_retry_names_then_review_flag(saved_guide, monkeypatch):
    calls = []

    def fake_sam(jpeg, concept):
        calls.append(concept)
        return [B(100, 80, 140, 120, 0.8)] if concept == "nut" else []

    monkeypatch.setattr(meta, "sam_boxes", fake_sam)
    monkeypatch.setattr(keyframes, "simpler_names", lambda part: ["nut"] if part == "axle nut" else [])
    guide = keyframes.build_keyframes("demo")

    s1, s2 = guide.steps
    assert s1.needs_review and s1.highlight is None            # "bolt": never found
    assert not s2.needs_review and s2.highlight_part == "nut"  # "axle nut" failed, "nut" worked
    assert (store.folder("demo") / "step_2.jpg").stat().st_size > 1000
    assert "axle nut" in calls and "nut" in calls


def test_simpler_names_retries_an_empty_reply(monkeypatch):
    # Observed live: the first names call came back empty (out=400, no text).
    replies = iter(["", json.dumps({"names": ["nut", "bolt"]})])
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: next(replies))
    assert keyframes.simpler_names("axle nut") == ["nut", "bolt"]


def test_simpler_names_gives_up_cleanly(monkeypatch):
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: "")
    assert keyframes.simpler_names("axle nut") == []
