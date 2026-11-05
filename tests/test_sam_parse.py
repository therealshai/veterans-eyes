from pathlib import Path

from backend.meta import parse_sam_boxes

FIXTURES = Path(__file__).parent / "fixtures"

DOCS_EXAMPLE = ("<0f>0<|box;x1=353;y1=382;x2=453;y2=427;w=537;h=561|><|mask;x=0;y=0;data=46,101,~ab|>,"
                "1<|box;x1=260;y1=382;x2=340;y2=427;w=537;h=561;c=0.96|><|mask;x=0;y=0;data=46,81,~cd|>")


def test_parses_the_documented_format():
    boxes = parse_sam_boxes(DOCS_EXAMPLE)
    assert len(boxes) == 2
    assert (boxes[0].x1, boxes[0].y2, boxes[0].w) == (353, 427, 537)
    assert boxes[1].score == 0.96


def test_empty_and_garbage():
    assert parse_sam_boxes("") == []
    assert parse_sam_boxes("<|box;x1=oops|>") == []


def test_parses_real_wire_output():
    # Verbatim sam-3.1 answer for "hand" (one_bit masks, confidences on).
    boxes = parse_sam_boxes((FIXTURES / "sam_hand_response.txt").read_text())
    assert len(boxes) == 4
    assert [(b.x1, b.y1, b.x2, b.y2) for b in boxes][0] == (107, 86, 115, 95)
    assert all(0.0 < (b.score or 0) <= 1.0 for b in boxes)
    assert all((b.w, b.h) == (796, 448) for b in boxes)
