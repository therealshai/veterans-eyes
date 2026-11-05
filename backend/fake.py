"""Demo mode: every Meta call answered with canned replies, nothing spent.

On when:   VE_FAKE=1, or no META_API_KEY in .env (so judges can run the repo without a key)
Off when:  VE_FAKE=0, or a key is present and VE_FAKE is unset
The app shows a "Demo mode" label whenever it is on (GET /api/config).
"""
import asyncio
import json
import os
import time
from pathlib import Path

from backend import meta
from backend.config import API_KEY
from backend.models import Box

_flag = os.getenv("VE_FAKE")
ENABLED = _flag == "1" or (_flag != "0" and not API_KEY)


def _guide_json(prompt: str) -> str:
    """A plausible 4-step guide spread over the video, so 'New guide' works in demo mode."""
    duration = 60.0
    for line in prompt.splitlines():
        if "Video length:" in line:
            try:
                duration = float(line.split("Video length:")[1].split("seconds")[0].strip())
            except ValueError:
                pass
    name = prompt.split('source_video: "')[1].split('"')[0] if 'source_video: "' in prompt else "video.mp4"
    q = duration / 4
    steps = [
        ("Remove the four cover screws", ["cover screw"], ["Phillips screwdriver"], ["Keep the long screw apart"], ["Don't drop screws into the engine bay"], True, "four screws out, long one set apart"),
        ("Lift off the cover", ["cover"], [], ["Lift from the bottom edge"], [], False, "cover off, clips intact"),
        ("Check the part and clean it", ["filter"], [], ["Hold it up to the light"], [], False, "part clean, no tears"),
        ("Refit the cover and screws", ["cover"], ["Phillips screwdriver"], ["Snug, don't force it"], ["Overtightening cracks the plastic"], True, "cover flush, long screw top left"),
    ]
    return json.dumps({
        "title": "Demo guide (canned steps)", "domain": "two-wheeler", "source_video": name, "duration_s": duration,
        "steps": [dict(step_no=i + 1, start_s=round(q * i, 2), end_s=round(q * (i + 1), 2), instruction=s[0], parts=s[1],
                       tools=s[2], expert_tips=s[3], warnings=s[4], critical=s[5], check_hint=s[6]) for i, s in enumerate(steps)],
    })


def _respond(model, parts, *, schema=None, schema_name="answer", fast=False):
    if schema_name == "guide":
        time.sleep(2.0)
        return _guide_json(parts[0].get("text", ""))
    return _spark(parts, schema=schema, schema_name=schema_name, fast=fast)


def _spark(parts, *, schema=None, schema_name="answer", fast=True):
    time.sleep(1.5)
    if schema_name == "verdict":
        n = int(time.time()) % 3
        return json.dumps([
            {"verdict": "match", "say": "Looks the same as the expert's. Carry on."},
            {"verdict": "fix", "say": "That's the wrong screw. Use the long one at the top left."},
            {"verdict": "unclear", "say": "Move the camera closer to the cover."},
        ][n])
    if schema_name == "names":
        return json.dumps({"names": ["screw", "bolt"]})
    return "Turn it anticlockwise, a quarter turn at a time. Snug is enough."


def _sam(jpeg, concept):
    time.sleep(1.0)
    from backend.media import image_size
    w, h = image_size(jpeg)
    if concept == "hand":
        return [Box(x1=int(w * .35), y1=int(h * .30), x2=int(w * .70), y2=int(h * .75), w=w, h=h, score=0.9)]
    return [Box(x1=int(w * .40), y1=int(h * .35), x2=int(w * .58), y2=int(h * .60), w=w, h=h, score=0.9)]


async def _asr(audio, to_phone):
    n = 0
    while (chunk := await audio.get()) is not None:
        n += len(chunk)
        await to_phone({"type": "partial", "text": "which screw"})
    await asyncio.sleep(0.4)
    await to_phone({"type": "final", "text": "Which screw do I take out first?" if n else ""})


def enable() -> None:
    from backend.live import asr_relay
    meta.spark = _spark
    meta.respond = _respond
    meta.sam_boxes = _sam
    meta.upload_file = lambda path: f"demo-file-{Path(path).name}"
    asr_relay._meta_stream = _asr
    print("[demo] Demo mode: Meta calls are answered with canned replies, nothing is spent. "
          "Add META_API_KEY to .env (see .env.example) for real answers.")
