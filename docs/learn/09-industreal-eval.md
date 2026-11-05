# 09 · The IndustReal score (`backend/eval/industreal.py`)

**One idea:** run the exact checkpoint the phone uses on footage where the mistakes are already labeled.

## The data
IndustReal: 84 egocentric videos (HoloLens 2, 10 fps JPEG frames) of people assembling a toy car;
38 labeled mistakes in 35 videos (wrong part, wrong orientation, skipped step). Apache-2.0, so it
can appear in the public video with credit. No audio, so no narrated expert: the "expert image"
for a step is the same step done correctly in another recording.

Per recording:
- `PSR_labels.csv`: frames where a step was completed correctly
- `PSR_labels_with_errors.csv`: the same plus wrong completions ("incorrectly installed rear wheel assy")
A row in the second file but not the first is a mistake.

## What the script does
1. Finds every recording under the folder you give it.
2. Builds a reference per step from a correct completion, preferring recordings with no mistakes.
3. Tests every completion in recordings that contain mistakes (right and wrong ones), 1 s after
   the labeled frame (`--offset 10`) so the hands have moved off the part.
4. Calls `coach.judge(step, expert_image, frame)`: Spark, minimal reasoning, strict JSON verdict.
5. Appends each answer to `docs/eval/industreal_runs.jsonl` (a rerun skips what's done) and writes
   `docs/industreal_results.md`.

## The numbers
| Number | Meaning | Good |
|---|---|---|
| Mistakes caught | wrong steps judged "fix" ÷ wrong steps | high |
| False alarms | right steps judged "fix" ÷ right steps | low |
| Can't see | "unclear" ÷ all | low; it's honest, not wrong |
A model that always says "fix" catches 100% with 100% false alarms; always report both.

## Reading the labels
The CSV column order isn't documented, so each row is read by shape: the cell ending in `.jpg`
(or a long number) is the frame, a small integer is the step id, the longest text is the
description. `--dry-run` prints the first five pairs so you can confirm before spending.

## Commands
```
python -m backend.eval.industreal ~/IndustReal --dry-run        # free: counts and 5 examples
python -m backend.eval.industreal ~/IndustReal --max-calls 20   # cheap first look
python -m backend.eval.industreal ~/IndustReal                  # all of it, resumable
```
