# 01 · The guide contract (`backend/models.py`)

**One idea:** every module agrees on one data shape, the guide, and Pydantic enforces it.

## What a Pydantic model does
A class with typed fields. `GuideDraft.model_validate_json(text)` turns JSON text into a
Python object, or raises `ValidationError` saying exactly which field is wrong.
```python
class StepDraft(BaseModel):
    step_no: int
    parts: list[str]
```
`model_dump()` goes the other way (object → dict), `model_dump_json()` → JSON text.

## Two layers, on purpose
| Class | Who fills it | Why separate |
|---|---|---|
| `StepDraft`, `GuideDraft` | Wonder | Strict JSON mode: **every field required, no extras**. A default (`= []`) drops a field from `required` and strict mode refuses the schema |
| `Step`, `Guide` | our pipeline | Adds fields Wonder must not invent: `keyframe`, `highlight`, `needs_review`, `status` |
`Step(StepDraft)` is inheritance: Step has all of StepDraft's fields plus its own.

## The validator
`@model_validator(mode="after")` runs once all fields are parsed, so it can compare steps:
numbering 1..n, end after start, no overlap (0.5 s grace), inside the video, at least one part.
Its error messages are written for a model to read: on failure, `extract_guide.py` sends the
exact message back to Wonder and asks for a corrected answer.

## The schema Wonder receives
`strict_schema(GuideDraft)` = `GuideDraft.model_json_schema()` flattened: nested `$ref`s are
copied in place and `title`s dropped, because some providers reject `$ref` in strict mode.
Only annotation titles go: a property actually named `title` stays, or `required` breaks (real 400).
See it: `python -c "from backend.models import *; import json; print(json.dumps(strict_schema(GuideDraft), indent=1))"`

## `Box`
SAM returns rectangles in pixels. Two overlap measures:
- `iou` = overlap ÷ union. Standard, but a hand (big) on a bolt (small) scores near 0.
- `covered_by` = overlap ÷ the part's own area. "How much of the bolt is under the hand": 1.0
  when the hand covers it. This is what keyframes use (test: `test_box_overlap`).

**Check yourself:** why would `tools: list[str] = []` break Wonder's call?
