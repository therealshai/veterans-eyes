# 06 · The API (`backend/app.py`, `backend/store.py`, `backend/expert/pipeline.py`)

**One idea:** one FastAPI process serves the API, the voice socket, and the built app.

## Routes
| Route | Does |
|---|---|
| `GET /api/config` | `{"demo": true}` when model answers are canned (drives the app's Demo badge) |
| `GET /api/health` | `{"ok": true}` liveness |
| `GET /api/guides` | cards for the home screen |
| `POST /api/guides` (form: video, title, domain, model) | saves the video, answers **202** at once, runs `pipeline.run` in the background |
| `GET /api/guides/{id}` | `{"job": progress, "guide": ...}`; the app polls it every 2 s while processing |
| `PUT /api/guides/{id}` | the senior's edits, validated by the same `Guide` model |
| `POST /api/guides/{id}/publish` | ready for juniors |
| `GET /api/guides/{id}/files/{name}` | keyframe JPEGs and the video |
| `POST /api/coach/ask`, `/check` | form fields + a `frame` JPEG upload |
| `WS /ws/asr` | the voice relay |
| `/` | `frontend/dist`, mounted last so API routes win |

## Background jobs
Wonder takes ~1 minute, longer than a request should wait. `BackgroundTasks.add_task` runs the
pipeline after the response is sent; `job.json` carries `status` and `progress` for the app to show
("Watching the video and writing steps", "Highlighting step 3 of 8").

## Blocking calls in an async server
Model calls block for seconds. `run_in_threadpool(coach.ask, ...)` moves them to a worker thread,
so the server keeps serving other requests (and the voice socket) meanwhile.

## Safety
Guide ids and file names are checked against strict patterns (`store.folder`, `store.file_path`),
so `../../.env` is refused; `.json` files are never served. The API key stays on the server.

## Storage
Files, not a database: `data/guides/<id>/` holds everything for one guide. `save_guide` writes to
a temp file and renames it, so a reader never sees half a file.

**Try:** `uvicorn backend.app:app --reload`, open http://localhost:8000/docs, run `/api/coach/ask`
with guide id `egoexo_repair_clip`, step 1, and one of the fixture frames.
