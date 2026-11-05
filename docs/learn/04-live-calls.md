# 04 · Ask and check (`backend/live/coach.py`)

**One idea:** the live calls send little, ask for little, and run side by side.

## ask: "which way do I turn it?"
Prompt = voice rules + the step (instruction, parts, tools, **the expert's tips**, warnings, the
done-looks-like hint) + the question + the current camera frame. Spark with `fast=True`
(minimal reasoning, 1200-token cap — the cap covers hidden reasoning too) → 1–2 sentences,
spoken by the phone. A reply cut off by the cap is retried once with double the cap
(`meta.respond`); a still-truncated answer is never returned mid-sentence.
Rules in the prompt: no lists or markdown (it will be spoken), never say "safe", say where to point
the camera when the photo isn't enough.

## check: "show me before you continue"
Two calls **at the same time** (`_pool.submit` twice, then `.result()` twice):

| Call | Input | Output |
|---|---|---|
| Spark verdict | expert keyframe + junior frame + check hint | `{"verdict": "match"/"fix"/"unclear", "say": "..."}` (strict JSON) |
| SAM | junior frame + the part name that worked in the keyframe | box of the part in the junior's view |

Sequential would be 3.4 + 3.2 = 6.6 s; parallel measured 4.0 s median (Oct 27).
If SAM fails, the check still returns the verdict: a missing highlight is not fatal.
A verdict outside the three values becomes "unclear": the coach never guesses.

## Latency budget for one spoken question
| Stage | Time |
|---|---|
| Final transcript after the button is released | 0.4 s |
| Upload frame + Spark fast | ~3.9 s |
| Phone starts speaking | ~0.1 s |
| **Total** | **~4.4 s** |

**Check yourself:** why do both live calls use `fast=True`, but `extract_guide` doesn't?
