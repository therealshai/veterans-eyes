# Speed test — 2026-11-03 21:41

Seconds. 5 counted runs per call (2 for Wonder), after one uncounted warm-up for the cheap calls.

| Call | OK | Median | Slowest | Sample output |
|---|---|---|---|---|
| 1. Spark: plain answer | 5/5 | 8.22 | 10.35 |  |
| 2. Spark: JSON verdict | 5/5 | 8.80 | 11.17 |  |
| 3. SAM 3.1: segment one prompt | 5/5 | 3.19 | 5.35 |  |
| 1f. Spark: plain answer, minimal reasoning | 5/5 | 4.19 | 6.25 | The person's hand is touching a bicycle wheel. |
| 2f. Spark: JSON verdict, minimal reasoning | 4/5 | 4.26 | 6.04 | {'reason': 'Table layout does not match: Image 1 shows two long black tools side-by-side in center, Image 2 shows only one long black tool with different placem |
| 2f+3. Checkpoint: Spark + SAM in parallel | 5/5 | 5.25 | 8.17 | {'verdict': {'reason': 'Image 2 does not match Image 1 workbench layout: the expert reference shows two long black tools side-by-side at the back of the bench,  |
| 4a. Transcribe: file | 5/5 | 1.91 | 2.77 |  |
| 4b. Transcribe: realtime (wait after speech) | 5/5 | 0.40 | 1.03 |  |
| ↳ connect | | 1.48 | 1.64 | |
| ↳ first_partial | | 10.56 | 11.18 | |
| 5. Wonder: video + audio | 2/2 | 46.94 | 51.60 | The video is a multi-angle recording of a single job - fitting the front wheel to a bicycle already mounted on a blue repair stand. The same action is shown in |
| ↳ upload | | 10.85 | 10.89 | |
| ↳ analysis | | 38.42 | 40.70 | |

**Decision:** Checkpoint (measured in parallel) = 5.25 s: 5–10 s, so send fewer frames and shorter prompts.

## Errors

- 2f. Spark: JSON verdict, minimal reasoning: `run 2: JSONDecodeError: Unterminated string starting at: line 1 column 12 (char 11)`

## Nov 3 vs Oct 29 (live medians; slowest in brackets)
- 1f answer: 3.91 (4.65) → **4.19 (6.25)** (first Nov 3 run: 3.39)
- 2f verdict: 3.40 (4.34) → **4.26 (6.04)**, 4/5 OK (first Nov 3 run: 4.27, 5/5)
- 2f+3 checkpoint: 3.98 (5.13) → **5.25 (8.17)** — over the 5 s design rule
- 2f run 2 hit the 400-token cap mid-JSON (out_tokens=400, truncated): the 400 cap is too tight for the verdict path. Prescribed next step: re-measure 5 calls at max_output_tokens 800 (needs 5 Spark calls of fresh budget).

## Nov 3 per-call output tokens (re-measure run; w = warm-up)
1f answer: w (not captured — line lost to output truncation), then
run 1: 4.22 s, out=227; run 2: 4.19 s, out=253; run 3: 6.25 s, out=183; run 4: 3.52 s, out=190; run 5: 2.51 s, out=186. All non-empty.
2f verdict: w: out=314; run 1: 6.04 s, out=340; run 2: TRUNCATED, out=400; run 3: 3.26 s, out=222; run 4: 4.57 s, out=259; run 5: 3.95 s, out=332. All non-empty (run 2 cut off mid-string).
Takeaway: minimal reasoning still spends ~150–370 tokens here, so a ~30-token JSON verdict can hit the 400 cap. The visible answers are short; the budget goes to thinking.
