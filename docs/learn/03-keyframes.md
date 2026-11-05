# 03 · Highlighted keyframes (`backend/expert/keyframes.py`)

**One idea:** the best picture of a step is the moment the hand touches the part.

## Per step
1. `media.sample_times(start, end, 5)`: 5 times evenly inside the step, away from its edges.
2. `media.frame_at(video, t)`: ffmpeg grabs one JPEG at t (scaled to ≤960 px wide: faster uploads).
3. SAM on every frame for **"hand"** and for the **step's first part**: 10 requests, all in flight at
   once through a `ThreadPoolExecutor` (8 workers). SAM takes one concept per request.
4. `pick_keyframe` applies the rules:

| Found | Keyframe |
|---|---|
| hand and part overlap | frame where the hand covers most of the part (`covered_by`) |
| part, no contact | the most confident part (then biggest) |
| nothing | middle frame, `needs_review = True` |

5. Nothing found → `simpler_names` asks Spark for two plainer names ("axle nut" → "nut", "bolt")
   and tries again once.
6. `media.draw_highlight` draws an amber box + label → `step_3.jpg`; the step records
   `keyframe`, `keyframe_s`, `highlight`, `highlight_part`.

## SAM's answer format
Text, not JSON: `<|box;x1=353;y1=382;x2=453;y2=427;w=537;h=561;c=0.96|>` per object.
x1,y1 top-left, x2,y2 bottom-right, **pixels**; w,h image size; c confidence (we ask for it with
`metadata={"include_confidence": "true"}`). Empty text = nothing found. Parsed by `meta.parse_sam_boxes`.

## Threads, in one paragraph
A SAM call spends ~3 s waiting on the network, doing nothing. Threads let 8 such waits overlap, so
10 calls take ~4 s instead of ~30 s. Python's GIL doesn't matter here: waiting releases it.

## Cost
~10 SAM images per step; 8 steps ≈ 80 images ≈ $0.20 at $2.50 per 1,000.

**Check yourself:** why `covered_by` and not IoU for "hand on bolt"? (`test_box_overlap`)
