"""
Every call to Meta's API goes through this file. Nothing else imports the client.

Why one file: the request shapes (content parts, JSON schema format, SAM's
box grammar) live in one place, and tests replace these functions with fakes,
so no test ever spends credits.
Learn notes: 02 (Wonder), 03 (SAM), 04 (Spark).
"""
import base64
import re
import time
from pathlib import Path

from backend.config import SAM_MODEL, SPARK_FAST, SPARK_MODEL, get_client
from backend.models import Box


# ── Content parts: the pieces of one user message ───────────────────────────

def text_part(text: str) -> dict:
    return {"type": "input_text", "text": text}


def image_part(jpeg: bytes) -> dict:
    """JSON can't carry bytes, so images travel as base64 text in a data URL."""
    b64 = base64.b64encode(jpeg).decode("ascii")
    return {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}


def file_part(file_id: str) -> dict:
    return {"type": "input_file", "file_id": file_id}


def _message(parts: list[dict]) -> list[dict]:
    return [{"type": "message", "role": "user", "content": parts}]


# ── Calls ───────────────────────────────────────────────────────────────────

def upload_file(path: Path) -> str:
    """Upload a video once; later calls refer to it by id."""
    with path.open("rb") as f:
        return get_client().files.create(file=f, purpose="user_data").id


def respond(model: str, parts: list[dict], *, schema: dict | None = None,
            schema_name: str = "answer", fast: bool = False) -> str:
    """One model call. With a schema, the answer is JSON that matches it (strict mode).
    fast=True adds minimal reasoning + a short output cap: for live calls only.
    A reply cut off by the token cap (or empty) is retried once with double the
    cap; a still-truncated reply is kept only if it ends a sentence, else raises."""
    kwargs = {}
    if schema is not None:
        kwargs["text"] = {"format": {"type": "json_schema", "name": schema_name,
                                     "schema": schema, "strict": True}}
    if fast:
        kwargs.update(SPARK_FAST)
    text, status, reason = "", "?", None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        response = get_client().responses.create(model=model, input=_message(parts), **kwargs)
        usage = getattr(response, "usage", None)
        text = response.output_text or ""
        status = getattr(response, "status", "completed")
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details else None
        print(f"[meta] {model} try{attempt} {time.perf_counter() - t0:.1f}s"
              + (f" in={usage.input_tokens} out={usage.output_tokens}" if usage else "")
              + (f" {status}/{reason}" if status != "completed" or not text.strip() else ""))
        if status == "completed" and text.strip():
            return text
        if attempt == 1:
            if kwargs.get("max_output_tokens"):
                kwargs["max_output_tokens"] *= 2
            print(f"[meta] {model} incomplete ({reason or 'empty'}), retrying once"
                  + (f" with {kwargs['max_output_tokens']} tokens" if kwargs.get("max_output_tokens") else ""))
    if text.strip() and text.strip()[-1] in ".!?":
        print(f"[meta] {model} keeping complete-looking reply despite {status}/{reason}")
        return text
    raise RuntimeError(f"{model} reply incomplete after retry (status={status}, reason={reason})")


def spark(parts: list[dict], *, schema: dict | None = None, schema_name: str = "answer",
          fast: bool = True) -> str:
    return respond(SPARK_MODEL, parts, schema=schema, schema_name=schema_name, fast=fast)


# ── SAM 3.1 ─────────────────────────────────────────────────────────────────
# SAM answers in a text grammar, one record per object found, e.g.
#   <0f>0<|box;x1=353;y1=382;x2=453;y2=427;w=537;h=561;c=0.96|><|mask;...|>,1<|box;...|>
# x1,y1 = top-left, x2,y2 = bottom-right, in pixels; w,h = image size; c = confidence.
# No match = empty text. One concept (e.g. "bolt") per request.

_BOX = re.compile(r"<\|box;([^|]*)\|>")


def parse_sam_boxes(output: str) -> list[Box]:
    boxes = []
    for record in _BOX.findall(output or ""):
        fields = dict(kv.split("=", 1) for kv in record.split(";") if "=" in kv)
        try:
            boxes.append(Box(
                x1=int(float(fields["x1"])), y1=int(float(fields["y1"])),
                x2=int(float(fields["x2"])), y2=int(float(fields["y2"])),
                w=int(float(fields["w"])), h=int(float(fields["h"])),
                score=float(fields["c"]) if "c" in fields else None,
            ))
        except (KeyError, ValueError):
            continue    # a record we can't read is skipped, not fatal
    return boxes


def sam_boxes(jpeg: bytes, concept: str) -> list[Box]:
    """Every instance of `concept` in the image, best first."""
    t0 = time.perf_counter()
    response = get_client().responses.create(
        model=SAM_MODEL,
        input=_message([text_part(concept), image_part(jpeg)]),
        metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
    )
    boxes = parse_sam_boxes(response.output_text or "")
    print(f"[meta] sam '{concept}' {time.perf_counter() - t0:.1f}s -> {len(boxes)} found")
    return sorted(boxes, key=lambda b: (b.score or 0, b.area), reverse=True)
