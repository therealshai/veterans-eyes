import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.models import Box, GuideDraft, strict_schema
from tests.conftest import guide_dict, step

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_guide_parses():
    g = GuideDraft.model_validate(guide_dict())
    assert [s.step_no for s in g.steps] == [1, 2]


@pytest.mark.parametrize("steps, message", [
    ([], "no steps"),
    ([step(2, 0, 3)], "1, 2, 3"),
    ([step(1, 3, 2)], "must be after"),
    ([step(1, 0, 3), step(2, 1, 4)], "before step 1 ends"),
    ([step(1, 0, 9)], "after the video ends"),
    ([step(1, 0, 3, parts=[" "])], "names no parts"),
])
def test_bad_guides_are_rejected_with_a_clear_reason(steps, message):
    with pytest.raises(ValidationError, match=message):
        GuideDraft.model_validate(guide_dict(steps=steps))


def test_extra_keys_are_refused():
    with pytest.raises(ValidationError):
        GuideDraft.model_validate(guide_dict(extra="x"))


def test_strict_schema_is_flat_and_complete():
    s = strict_schema(GuideDraft)
    text = json.dumps(s)
    assert "$ref" not in text and "title" not in s
    item = s["properties"]["steps"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])      # strict mode: all required


def test_real_wonder_answer_validates():
    # Verbatim Wonder answer for the CC BY chain-cleaning video (the demo's senior guide).
    g = GuideDraft.model_validate_json((FIXTURES / "wonder_guide_raw.json").read_text())
    assert g.title == 'Clean and lubricate the motorcycle chain'
    assert [s.step_no for s in g.steps] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert sum(s.critical for s in g.steps) == 3


def test_strict_schema_keeps_a_property_named_title():
    # Real Meta 400: required listed "title" after the flattener ate the property.
    s = strict_schema(GuideDraft)
    assert s["properties"]["title"] == {"type": "string"}
    assert set(s["required"]) == set(s["properties"])
    assert "title" not in s                                       # the annotation is still gone


def test_box_overlap():
    hand = Box(x1=0, y1=0, x2=100, y2=100, w=200, h=200)
    bolt = Box(x1=80, y1=80, x2=90, y2=90, w=200, h=200)
    assert bolt.covered_by(hand) == 1.0          # hand fully covers the bolt...
    assert bolt.iou(hand) < 0.02                 # ...yet IoU stays tiny: why we use covered_by
