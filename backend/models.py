"""
The guide contract. Every module reads these classes.

Two layers:
  StepDraft / GuideDraft  what Wonder must return. Strict JSON mode needs every
                          field required (no defaults) and no extra keys.
  Step / Guide            what we store: the draft plus fields our pipeline adds
                          later (keyframe, highlight box, review flag, status).
Learn note: docs/learn/01-guide-contract.md
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class Box(BaseModel):
    """A rectangle in pixels, as SAM returns it: top-left (x1, y1), bottom-right (x2, y2).
    w, h are the size of the whole image the box was found in."""

    x1: int
    y1: int
    x2: int
    y2: int
    w: int
    h: int
    score: float | None = None

    @property
    def area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    def intersection(self, other: "Box") -> int:
        ix = max(0, min(self.x2, other.x2) - max(self.x1, other.x1))
        iy = max(0, min(self.y2, other.y2) - max(self.y1, other.y1))
        return ix * iy

    def iou(self, other: "Box") -> float:
        """Intersection over union: 0 = no overlap, 1 = the same box."""
        inter = self.intersection(other)
        union = self.area + other.area - inter
        return inter / union if union else 0.0

    def covered_by(self, other: "Box") -> float:
        """Share of THIS box that the other box covers (0..1).
        Better than IoU for "is the hand on the bolt": a hand is much bigger than a
        bolt, so their IoU stays small even when the hand covers the bolt fully."""
        return self.intersection(other) / self.area if self.area else 0.0


# ── What Wonder returns ─────────────────────────────────────────────────────

class StepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_no: int
    start_s: float
    end_s: float
    instruction: str
    parts: list[str]
    tools: list[str]
    expert_tips: list[str]
    warnings: list[str]
    critical: bool
    check_hint: str


class GuideDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    domain: str
    source_video: str
    duration_s: float
    steps: list[StepDraft]

    @model_validator(mode="after")
    def check_steps(self):
        """Runs after every field is parsed. Each message is precise on purpose:
        on failure it is sent back to Wonder for one corrected answer."""
        if not self.steps:
            raise ValueError("The guide has no steps.")
        prev_end = 0.0
        for i, s in enumerate(self.steps, start=1):
            if s.step_no != i:
                raise ValueError(f"Step numbers must be 1, 2, 3 ... in order; found {s.step_no} at position {i}.")
            if s.end_s <= s.start_s:
                raise ValueError(f"Step {i}: end_s ({s.end_s}) must be after start_s ({s.start_s}).")
            if s.start_s < prev_end - 0.5:
                raise ValueError(f"Step {i} starts at {s.start_s}s, before step {i - 1} ends at {prev_end}s.")
            if s.end_s > self.duration_s + 1:
                raise ValueError(f"Step {i} ends at {s.end_s}s, after the video ends ({self.duration_s}s).")
            if not any(p.strip() for p in s.parts):
                raise ValueError(f"Step {i} names no parts; name at least one visible object.")
            prev_end = s.end_s
        return self


# ── What we store ───────────────────────────────────────────────────────────

class Step(StepDraft):
    keyframe: str | None = None            # file name inside the guide folder, e.g. step_3.jpg
    keyframe_s: float | None = None        # time in the video the keyframe was taken
    highlight: Box | None = None           # where the part is in the keyframe
    highlight_part: str | None = None      # the name SAM found it by (may be a retry name)
    needs_review: bool = False             # no part found: the senior should check this step


Status = Literal["processing", "draft", "published", "failed"]


class Guide(GuideDraft):
    id: str = ""
    status: Status = "draft"
    progress: str = ""                     # human-readable stage while processing
    error: str | None = None
    steps: list[Step]

    @classmethod
    def from_draft(cls, draft: GuideDraft, guide_id: str) -> "Guide":
        return cls.model_validate({**draft.model_dump(), "id": guide_id, "status": "draft"})


class GuideSummary(BaseModel):
    id: str
    title: str
    domain: str
    status: Status
    progress: str = ""
    steps: int
    critical_steps: int
    duration_s: float
    cover: str | None = None


def strict_schema(model: type[BaseModel]) -> dict:
    """The model's JSON schema, flattened for strict mode: nested models are copied
    in place of "$ref" links and "title" keys are dropped. Some providers reject
    $ref in strict schemas; a flat schema works everywhere."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            # Drop "title" only when it is a schema annotation (a string like
            # "GuideDraft"); a property actually NAMED "title" is a dict and stays.
            return {k: walk(v) for k, v in node.items()
                    if k != "title" or isinstance(v, dict)}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)
