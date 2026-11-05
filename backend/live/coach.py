"""
The two live calls the junior's phone makes. Both must answer in about 4 s.

    ask:   question + current camera frame + the step's text  --Spark (fast)-->  1-2 spoken sentences
    check: current frame vs the expert keyframe                --Spark (fast)-->  matches / fix / unclear
                                              at the same time --SAM-->           where the part is now

Measured Oct 27: Spark fast 3.4-3.9 s, SAM 3.2 s, both in parallel 4.0 s.
Learn note: docs/learn/04-live-calls.md
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from backend import meta, store
from backend.models import Box, Guide, Step

_pool = ThreadPoolExecutor(max_workers=8)      # shared: threads are reused across requests

VOICE_RULES = (
    "You are a calm senior mechanic coaching a junior through a repair, by voice. "
    "Answer in at most two short sentences, plain words, no lists, no markdown. "
    "Use the expert's tips when they answer the question. Never say something is safe. "
    "If the photo does not show enough, say what to point the camera at."
)


def _step_context(guide: Guide, step: Step) -> str:
    lines = [f"Job: {guide.title}. Step {step.step_no} of {len(guide.steps)}: {step.instruction}",
             f"Parts: {', '.join(step.parts)}."]
    if step.tools:
        lines.append(f"Tools: {', '.join(step.tools)}.")
    if step.expert_tips:
        lines.append("Expert's tips: " + " | ".join(step.expert_tips))
    if step.warnings:
        lines.append("Warnings: " + " | ".join(step.warnings))
    lines.append(f"Done correctly looks like: {step.check_hint}")
    return "\n".join(lines)


class AskResult(BaseModel):
    answer: str
    seconds: float


def ask(guide: Guide, step: Step, question: str, frame: bytes | None) -> AskResult:
    t0 = time.perf_counter()
    parts = [meta.text_part(f"{VOICE_RULES}\n\n{_step_context(guide, step)}\n\nThe junior asks: \"{question}\"")]
    if frame:
        parts.append(meta.image_part(frame))
    answer = meta.spark(parts).strip()
    if not answer:  # one retry: a single empty reply shouldn't end the conversation
        answer = meta.spark(parts).strip()
    return AskResult(answer=answer or "Sorry, I didn't catch that. Ask again?",
                     seconds=round(time.perf_counter() - t0, 2))


VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "say"],
    "properties": {
        "verdict": {"type": "string", "enum": ["match", "fix", "unclear"]},
        "say": {"type": "string"},
    },
}


class CheckResult(BaseModel):
    verdict: str            # match | fix | unclear
    say: str                # one sentence to speak
    highlight: Box | None   # where the step's part is in the junior's frame
    seconds: float


def judge(step_text: str, expert: bytes | None, frame: bytes) -> dict:
    """The checkpoint question, on its own: does `frame` show the step done like `expert`?
    Used live (below) and by the IndustReal evaluation (backend/eval/industreal.py)."""
    prompt = (
        f"{step_text}\n\n"
        + ("Image 1 is the expert doing this step. Image 2 is the junior's work now. " if expert
           else "The image is the junior's work now. ")
        + "Has the junior done this step correctly? verdict: 'match' if it looks right, "
        "'fix' if something is visibly wrong, 'unclear' if the photo can't tell. "
        "say: one short sentence for the junior; for 'fix' say exactly what to change; "
        "for 'unclear' say where to point the camera. Never say it is safe."
    )
    parts = [meta.text_part(prompt)] + ([meta.image_part(expert)] if expert else []) + [meta.image_part(frame)]
    try:
        data = json.loads(meta.spark(parts, schema=VERDICT_SCHEMA, schema_name="verdict"))
    except Exception:
        data = {}  # truncated or empty JSON: fall through to "unclear", never crash
    if data.get("verdict") not in ("match", "fix", "unclear"):
        data = {"verdict": "unclear", "say": "I couldn't judge that. Hold the camera closer and check again."}
    return data


def _verdict(guide: Guide, step: Step, frame: bytes) -> dict:
    expert = (store.folder(guide.id) / step.keyframe).read_bytes() if step.keyframe else None
    return judge(_step_context(guide, step), expert, frame)


def _locate(step: Step, frame: bytes) -> Box | None:
    name = step.highlight_part or step.parts[0]
    boxes = meta.sam_boxes(frame, name)
    return boxes[0] if boxes else None


def check(guide: Guide, step: Step, frame: bytes) -> CheckResult:
    t0 = time.perf_counter()
    verdict_job = _pool.submit(_verdict, guide, step, frame)     # both start now...
    locate_job = _pool.submit(_locate, step, frame)
    verdict = verdict_job.result()                                # ...and we wait for both
    try:
        box = locate_job.result()
    except Exception as e:                                        # a missing highlight is not fatal
        print(f"[check] SAM failed: {e}")
        box = None
    return CheckResult(verdict=verdict["verdict"], say=verdict["say"], highlight=box,
                       seconds=round(time.perf_counter() - t0, 2))
