"""
IndustReal evaluation: does our checkpoint catch real assembly mistakes?

IndustReal (Apache-2.0) has 84 egocentric videos of people assembling a toy car,
with 38 labeled mistakes across 35 of the videos. For every recording:
  PSR_labels.csv              frames where a step was completed CORRECTLY
  PSR_labels_with_errors.csv  the same, plus steps completed WRONGLY ("incorrectly installed ...")

For each completion frame we ask the same checkpoint the phone uses (coach.judge):
"Image 1 is the expert doing this step; image 2 is the junior now. Done right?"
Image 1 comes from ANOTHER recording where that step was done correctly.

    mistakes caught = wrong steps judged "fix"   / all wrong steps tested
    false alarms    = right steps judged "fix"   / all right steps tested
    can't see       = "unclear" answers          / all tested

Run:
    python -m backend.eval.industreal <unzipped val_p1 folder> --dry-run   # counts only, free
    python -m backend.eval.industreal <folder> --max-calls 20              # a cheap first look
    python -m backend.eval.industreal <folder>                             # everything (resumes)
Results: docs/industreal_results.md (+ docs/eval/industreal_runs.jsonl, so reruns skip done items)
Learn note: docs/learn/09-industreal-eval.md
"""
import argparse
import csv
import io
import json
import random
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from backend.config import ROOT
from backend.live import coach

RUNS_FILE = ROOT / "docs" / "eval" / "industreal_runs.jsonl"
REPORT_FILE = ROOT / "docs" / "industreal_results.md"
JOB = "Industrial assembly of a construction-toy car, following a fixed procedure."


@dataclass
class Completion:
    recording: str
    frame: str            # image file name in rgb/
    step_id: str
    description: str      # as labeled
    key: str              # the step, normalized: "incorrectly installed X" -> "installed x"
    wrong: bool


@dataclass
class Result:
    recording: str
    frame: str
    key: str
    wrong: bool
    verdict: str
    say: str
    reference: str


# ── Reading the labels ─────────────────────────────────────────────────────

_WRONG_WORDS = re.compile(r"^(incorrectly|incorrect|wrongly|wrong)\s+", re.I)


def normalize(desc: str) -> str:
    return re.sub(r"\s+", " ", _WRONG_WORDS.sub("", desc.strip())).lower()


def read_rows(path: Path) -> list[tuple[str, str, str]]:
    """(frame, step_id, description) per row. The column order isn't documented, so each
    row is read by shape: the image name, a small integer id, and the text."""
    rows = []
    with path.open(newline="") as f:
        for cells in csv.reader(f):
            cells = [c.strip() for c in cells if c.strip()]
            frame = next((c for c in cells if re.search(r"\.(jpe?g|png)$", c, re.I)), None) \
                or next((c for c in cells if re.fullmatch(r"\d{4,}", c)), None)
            step = next((c for c in cells if re.fullmatch(r"-?\d{1,3}", c) and c != frame), "")
            texts = [c for c in cells if c not in (frame, step) and re.search(r"[A-Za-z]{3}", c)]
            if frame and texts:
                rows.append((frame, step, max(texts, key=len)))
    return rows


def load_recording(rec: Path) -> list[Completion]:
    with_errors = rec / "PSR_labels_with_errors.csv"
    correct_file = rec / "PSR_labels.csv"
    correct = {(fr, normalize(d)) for fr, _, d in read_rows(correct_file)} if correct_file.exists() else None
    out = []
    for frame, step, desc in read_rows(with_errors):
        key = normalize(desc)
        wrong = bool(_WRONG_WORDS.match(desc)) or (correct is not None and (frame, key) not in correct)
        out.append(Completion(rec.name, frame, step, desc, key, wrong))
    return out


def frame_path(rec: Path, frame: str, offset: int) -> Path | None:
    """The labeled frame, `offset` frames later (hands often cover the part at the exact moment)."""
    rgb = rec / "rgb"
    files = sorted(p.name for p in rgb.iterdir()) if rgb.is_dir() else []
    name = frame if frame in files else next((f for f in files if f.startswith(frame) or f.split(".")[0].endswith(frame)), None)
    if name is None:
        return None
    i = min(files.index(name) + offset, len(files) - 1)
    return rgb / files[i]


def jpeg(path: Path, max_width: int = 960) -> bytes:
    img = Image.open(path).convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ── The run ────────────────────────────────────────────────────────────────

def plan(root: Path, offset: int, max_calls: int | None, seed: int = 7):
    recs = sorted({p.parent for p in root.rglob("PSR_labels_with_errors.csv")})
    by_rec = {r: load_recording(r) for r in recs}
    error_recs = {r for r, cs in by_rec.items() if any(c.wrong for c in cs)}

    # References: correct completions per step, clean recordings first.
    refs: dict[str, list[tuple[Path, Completion]]] = defaultdict(list)
    for r in sorted(recs, key=lambda r: r in error_recs):
        for c in by_rec[r]:
            if not c.wrong:
                refs[c.key].append((r, c))

    items = []
    for r in recs:
        for c in by_rec[r]:
            if r not in error_recs and not c.wrong:
                continue                          # clean recordings serve as references only
            ref = next(((rr, rc) for rr, rc in refs.get(c.key, []) if rr != r), None)
            junior, expert = frame_path(r, c.frame, offset), ref and frame_path(ref[0], ref[1].frame, offset)
            if junior and expert:
                items.append((c, junior, expert))
    wrong = [i for i in items if i[0].wrong]
    right = [i for i in items if not i[0].wrong]
    if max_calls and len(items) > max_calls:      # keep every mistake we can afford, fill with correct steps
        random.Random(seed).shuffle(right)
        wrong = wrong[:max_calls]
        right = right[:max(0, max_calls - len(wrong))]
    return recs, error_recs, wrong + right


def load_done() -> dict[tuple[str, str], Result]:
    if not RUNS_FILE.exists():
        return {}
    done = {}
    for line in RUNS_FILE.read_text().splitlines():
        if line.strip():
            r = Result(**json.loads(line))
            done[(r.recording, r.frame)] = r
    return done


def run_one(c: Completion, junior: Path, expert: Path) -> Result:
    step_text = f"{JOB}\nStep: {normalize(c.description)}.\nDone correctly looks like image 1."
    v = coach.judge(step_text, jpeg(expert), jpeg(junior))
    return Result(c.recording, c.frame, c.key, c.wrong, v["verdict"], v["say"], f"{expert.parent.parent.name}/{expert.name}")


def report(results: list[Result]) -> str:
    wrong = [r for r in results if r.wrong]
    right = [r for r in results if not r.wrong]
    caught = sum(r.verdict == "fix" for r in wrong)
    alarms = sum(r.verdict == "fix" for r in right)
    unclear = sum(r.verdict == "unclear" for r in results)
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"
    lines = [
        "# IndustReal checkpoint evaluation", "",
        "Same checkpoint the phone uses (Muse Spark, minimal reasoning) on IndustReal completion frames. "
        "Reference image: the same step done correctly in another recording.", "",
        "| Number | Value |", "|---|---|",
        f"| Mistakes caught | {pct(caught, len(wrong))} |",
        f"| False alarms on correct steps | {pct(alarms, len(right))} |",
        f"| Can't see clearly | {pct(unclear, len(results))} |",
        f"| Completions judged | {len(results)} |", "",
        "## Mistakes", "", "| Recording | Step | Verdict | What it said |", "|---|---|---|---|",
    ]
    lines += [f"| {r.recording} | {r.key} | {r.verdict} | {r.say.replace('|', '/')} |" for r in wrong]
    lines += ["", "Data: IndustReal (Schoonbeek et al., WACV 2024), Apache-2.0."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Checkpoint accuracy on IndustReal")
    ap.add_argument("root", type=Path, help="folder holding IndustReal recordings (searched recursively)")
    ap.add_argument("--offset", type=int, default=10, help="frames after the labeled one (10 = 1 s at 10 fps)")
    ap.add_argument("--max-calls", type=int, default=None, help="cap the number of model calls")
    ap.add_argument("--dry-run", action="store_true", help="count what would run; no model calls")
    ap.add_argument("--fake", action="store_true", help="canned model answers (tests the pipeline only)")
    args = ap.parse_args()

    recs, error_recs, items = plan(args.root, args.offset, args.max_calls)
    n_wrong = sum(c.wrong for c, _, _ in items)
    print(f"{len(recs)} recordings, {len(error_recs)} with mistakes; "
          f"{len(items)} completions to judge ({n_wrong} wrong, {len(items) - n_wrong} correct)")
    if args.dry_run or not items:
        print("\nPer recording (steps labeled / mistakes):")
        for r in recs:
            cs = load_recording(r)
            wrong = [c.description for c in cs if c.wrong]
            print(f"  {r.name:28s} {len(cs):3d} steps  {len(wrong)} mistakes"
                  + (f"  e.g. {wrong[0]!r}" if wrong else "  (clean: good expert video)"))
        print("\nFirst pairs to judge:")
        for c, j, e in items[:5]:
            print(f"  {'WRONG' if c.wrong else 'ok   '} {c.recording} {j.name}  vs  {e.parent.parent.name}/{e.name}  {c.description}")
        return
    if args.fake:
        from backend import fake
        fake.enable()

    done = load_done()
    todo = [i for i in items if (i[0].recording, i[0].frame) not in done]
    print(f"{len(items) - len(todo)} already judged, {len(todo)} to go")
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool, RUNS_FILE.open("a") as out:
        for c, res in zip(todo, pool.map(lambda i: _safe(run_one, *i), todo)):
            if res is None:
                continue
            out.write(json.dumps(asdict(res)) + "\n")
            out.flush()
            done[(res.recording, res.frame)] = res
            print(f"  {'WRONG' if res.wrong else 'ok   '} -> {res.verdict:8s} {res.recording} {res.key}")

    wanted = {(c.recording, c.frame) for c, _, _ in items}
    results = [r for k, r in done.items() if k in wanted]
    text = report(results)
    REPORT_FILE.write_text(text)
    print("\n" + "\n".join(text.splitlines()[5:11]))
    print(f"\nSaved {REPORT_FILE.relative_to(ROOT)}")


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"  error: {type(e).__name__}: {e}")
        return None


if __name__ == "__main__":
    main()
