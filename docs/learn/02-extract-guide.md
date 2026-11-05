# 02 · Expert video → guide (`backend/expert/extract_guide.py`)

**One idea:** upload once, ask once with a schema, save the raw answer before trusting it, retry once.

```
video --upload--> file_id --Wonder + prompt + schema--> raw JSON --save--> validate --> Guide
                                    ^                                       | fails
                                    +----- once more, with the error <------+
```

## Steps in `extract()`
1. `media.duration_s` reads the true length with ffprobe (the model's guess is overwritten).
2. `build_prompt` fills `{domain}`, `{duration_s}`, `{source_video}` in `backend/prompts/extract_guide.md`.
   The prompt lives in a file so every change shows up in git.
3. `meta.upload_file` → `file_id`. Uploading took ~11 s on Oct 27, so the retry reuses the id.
4. `meta.respond(WONDER_MODEL, [text, file], schema=...)` with `strict: True`: the reply must match.
5. `raw_1.json` is written **before** validation: a parsing bug never costs a second Wonder call
   (`--from-raw` re-checks it for free).
6. `ValidationError` → append the error text to the prompt, ask again → `raw_2.json`. A second
   failure raises; both answers are on disk to read.

## Why Wonder and not Spark here
Wonder hears the narration natively; Spark 1.3's docs say its audio is weaker. This call runs once
per guide (~50 s), so quality beats speed: no `fast=True` here. `--model spark` exists for cheap dry runs.

## Folder it writes
`data/guides/<id>/`: `video.mp4`, `job.json` (progress for the app), `raw_1.json`, `guide.json`.

**Try:** `python -m backend.expert.extract_guide fixtures/egoexo_repair_clip.mp4`, then edit the
prompt and run with `--from-raw` to see that validation alone is free.
