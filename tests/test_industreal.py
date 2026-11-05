"""The evaluation pipeline on a tiny made-up IndustReal folder (no model calls)."""
from PIL import Image

from backend.eval import industreal as ev


def make_rec(root, name, rows, correct_rows, color):
    rec = root / "recordings" / "val" / name
    (rec / "rgb").mkdir(parents=True)
    for i in range(40):
        Image.new("RGB", (64, 48), color).save(rec / "rgb" / f"{i:06d}.jpg")
    (rec / "PSR_labels_with_errors.csv").write_text("\n".join(rows) + "\n")
    (rec / "PSR_labels.csv").write_text("\n".join(correct_rows) + "\n")
    return rec


def test_labels_are_read_by_shape():
    assert ev.normalize("Incorrectly  installed Rear wheel assy") == "installed rear wheel assy"


def test_plan_and_scores(tmp_path, monkeypatch):
    ok = ["000005.jpg,1,Installed front chassis", "000010.jpg,2,Installed rear wheel assy"]
    make_rec(tmp_path, "clean_rec", ok, ok, (0, 200, 0))                       # references
    bad = ["000005.jpg,1,Installed front chassis", "000012.jpg,2,Incorrectly installed rear wheel assy"]
    make_rec(tmp_path, "error_rec", bad, bad[:1], (200, 0, 0))

    recs, error_recs, items = ev.plan(tmp_path, offset=2, max_calls=None)
    assert len(recs) == 2 and [r.name for r in error_recs] == ["error_rec"]
    assert sorted((c.key, c.wrong) for c, _, _ in items) == [("installed front chassis", False), ("installed rear wheel assy", True)]
    c, junior, expert = next(i for i in items if i[0].wrong)
    assert junior.name == "000014.jpg" and expert.parent.parent.name == "clean_rec"

    calls = []
    def fake_judge(step_text, expert_jpeg, frame_jpeg):
        calls.append(step_text)
        return {"verdict": "fix" if "rear wheel" in step_text else "match", "say": "x"}
    monkeypatch.setattr(ev.coach, "judge", fake_judge)
    results = [ev.run_one(*i) for i in items]
    text = ev.report(results)
    assert "Mistakes caught | 1/1 (100%)" in text and "False alarms on correct steps | 0/1 (0%)" in text
