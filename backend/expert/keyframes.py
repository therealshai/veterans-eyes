"""
One highlighted keyframe per step.

For each step: sample a few frames inside the step's time range, ask SAM where
the hand and the step's main part are in each frame, and keep the frame where
the hand touches the part (the moment of action). Draw an amber box on the part.

    sample 5 frames --SAM "hand" + SAM "<part>" per frame (in parallel)--> pick by rules --> step_3.jpg
                                   | part never found
                                   +--> ask Spark for 2 simpler names, try again --> still nothing: middle frame, needs_review

Run alone:  python -m backend.expert.keyframes <guide_id>
Learn note: docs/learn/03-keyframes.md
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from backend import media, meta, store
from backend.models import Box, Guide, Step

FRAMES_PER_STEP = 5
PARALLEL_CALLS = 8          # SAM requests in flight at once


@dataclass
class FrameFinding:
    t: float
    jpeg: bytes
    hands: list[Box]
    parts: list[Box]


@dataclass
class Pick:
    index: int
    box: Box | None
    reason: str             # "contact", "part", "none"


def pick_keyframe(findings: list[FrameFinding]) -> Pick:
    """The keyframe rules (also in the Oct 29 / Nov 2 plan):
      1. hand and part overlap  -> the frame where the hand covers most of the part
      2. part found, no contact -> the frame with the most confident (then biggest) part
      3. nothing found          -> the middle frame, flagged for review
    """
    best_contact, best_i, best_box = 0.0, -1, None
    for i, f in enumerate(findings):
        for part in f.parts:
            contact = max((part.covered_by(h) for h in f.hands), default=0.0)
            if contact > best_contact:
                best_contact, best_i, best_box = contact, i, part
    if best_i >= 0:
        return Pick(best_i, best_box, "contact")

    candidates = [(i, f.parts[0]) for i, f in enumerate(findings) if f.parts]
    if candidates:
        i, box = max(candidates, key=lambda c: ((c[1].score or 0), c[1].area))
        return Pick(i, box, "part")
    return Pick(len(findings) // 2, None, "none")


def _find_all(frames: list[tuple[float, bytes]], concepts: list[str], pool: ThreadPoolExecutor) -> dict:
    """SAM for every (frame, concept) pair at once. Returns {(frame_index, concept): [boxes]}."""
    jobs = {(i, c): pool.submit(meta.sam_boxes, jpeg, c) for i, (_, jpeg) in enumerate(frames) for c in concepts}
    out = {}
    for key, fut in jobs.items():
        try:
            out[key] = fut.result()
        except Exception as e:           # one failed call shouldn't sink the step
            print(f"[keyframes] SAM failed for {key[1]!r}: {e}")
            out[key] = []
    return out


def simpler_names(part: str) -> list[str]:
    """Ask Spark for two simpler, more visual names SAM may recognise."""
    schema = {"type": "object", "additionalProperties": False, "required": ["names"],
              "properties": {"names": {"type": "array", "items": {"type": "string"}}}}
    prompt = (f"An object detector could not find '{part}' in photos of a vehicle repair. "
              "Give two shorter, more common names for the same visible object, most likely first. "
              "One or two words each, e.g. 'axle nut' -> 'nut', 'bolt'.")
    for attempt in (1, 2):  # one retry: a single empty reply shouldn't doom the step
        reply = ""
        try:
            reply = meta.spark([meta.text_part(prompt)], schema=schema, schema_name="names")
            names = json.loads(reply)["names"]
        except Exception as e:
            print(f"[keyframes] names try {attempt} for {part!r}: {e} (reply {reply[:80]!r})")
            continue
        return [n.strip() for n in names if n.strip() and n.strip().lower() != part.lower()][:2]
    return []


def keyframe_step(guide: Guide, step: Step, pool: ThreadPoolExecutor) -> Step:
    video = store.folder(guide.id) / "video.mp4"
    times = media.sample_times(step.start_s, step.end_s, FRAMES_PER_STEP)
    frames = [(t, media.frame_at(video, t)) for t in times]

    names = [step.parts[0]]
    found_by, pick, findings = None, None, []
    while names:
        name = names.pop(0)
        results = _find_all(frames, ["hand", name], pool)
        findings = [FrameFinding(t, jpeg, results[(i, "hand")], results[(i, name)])
                    for i, (t, jpeg) in enumerate(frames)]
        pick = pick_keyframe(findings)
        if pick.reason != "none":
            found_by = name
            break
        if name == step.parts[0]:
            names += simpler_names(name)        # one round of retry names
            print(f"[keyframes] step {step.step_no}: '{name}' not found, trying {names}")

    chosen = findings[pick.index]
    label = found_by or step.parts[0]
    (store.folder(guide.id) / f"step_{step.step_no}.jpg").write_bytes(media.draw_highlight(chosen.jpeg, pick.box, label))
    return step.model_copy(update={
        "keyframe": f"step_{step.step_no}.jpg", "keyframe_s": chosen.t, "highlight": pick.box,
        "highlight_part": found_by, "needs_review": pick.reason == "none",
    })


def build_keyframes(guide_id: str) -> Guide:
    guide = store.load_guide(guide_id)
    if guide is None:
        raise SystemExit(f"No guide.json for {guide_id}: run extract_guide first.")
    with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
        steps = []
        for step in guide.steps:
            store.write_job(guide_id, progress=f"Highlighting step {step.step_no} of {len(guide.steps)}")
            steps.append(keyframe_step(guide, step, pool))
            s = steps[-1]
            print(f"  step {s.step_no}: {s.keyframe} at {s.keyframe_s}s "
                  f"{'REVIEW' if s.needs_review else 'found ' + repr(s.highlight_part)}")
    guide = guide.model_copy(update={"steps": steps})
    store.save_guide(guide)
    return guide


def main() -> None:
    ap = argparse.ArgumentParser(description="Highlighted keyframe per step")
    ap.add_argument("guide_id")
    guide = build_keyframes(ap.parse_args().guide_id)
    review = [s.step_no for s in guide.steps if s.needs_review]
    print(f"\nDone: {len(guide.steps)} keyframes in data/guides/{guide.id}/"
          + (f"  needs review: steps {review}" if review else ""))


if __name__ == "__main__":
    main()
