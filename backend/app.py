"""
The web server: one process serves the API, the voice WebSocket and the built app.

    uvicorn backend.app:app --reload          then http://localhost:8000/docs to try the API

Routes
    GET  /api/config                     {"demo": true} when model calls are canned
    GET  /api/guides                     list (cards on the home screen)
    POST /api/guides                     upload an expert video -> background job
    GET  /api/guides/{id}                one guide (poll while status = processing)
    PUT  /api/guides/{id}                save the senior's edits
    POST /api/guides/{id}/publish        mark ready for juniors
    GET  /api/guides/{id}/files/{name}   keyframe images and the video
    POST /api/coach/ask                  question + frame -> short spoken answer
    POST /api/coach/check                frame -> verdict + highlight
    WS   /ws/asr                         phone mic -> transcript
    /                                    the built frontend (frontend/dist)
Learn note: docs/learn/06-api.md
"""
import shutil

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend import fake, store
from backend.config import FRONTEND_DIST
from backend.expert import pipeline
from backend.live import asr_relay, coach
from backend.models import Guide, GuideSummary

app = FastAPI(title="Veteran's Eyes", version="0.1")
if fake.ENABLED:
    fake.enable()
for _gid in store.seed_demo_guides():
    print(f"[demo] added sample guide {_gid}")
MAX_FRAME_BYTES = 4_000_000


def _guide_or_404(guide_id: str) -> Guide:
    try:
        guide = store.load_guide(guide_id)
    except ValueError:
        raise HTTPException(400, "Bad guide id")
    if guide is None:
        raise HTTPException(404, "Guide not found or still processing")
    return guide


def _step_or_404(guide: Guide, step_no: int):
    step = next((s for s in guide.steps if s.step_no == step_no), None)
    if step is None:
        raise HTTPException(404, f"Step {step_no} not found")
    return step


async def _read_frame(frame: UploadFile | None) -> bytes | None:
    if frame is None:
        return None
    data = await frame.read()
    if len(data) > MAX_FRAME_BYTES:
        raise HTTPException(413, "Frame too large; send a JPEG under 4 MB")
    return data or None


# ── Guides ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    """demo = model calls are canned (no API key, or VE_FAKE=1). The app shows a label."""
    return {"demo": fake.ENABLED}


@app.get("/api/guides", response_model=list[GuideSummary])
def list_guides():
    return store.list_guides()


@app.post("/api/guides", response_model=GuideSummary, status_code=202)
def create_guide(background: BackgroundTasks, video: UploadFile = File(...), title: str = Form(""),
                 domain: str = Form("two-wheeler"), model: str = Form("wonder")):
    """Save the upload, answer at once (202 Accepted), and process in the background.
    The app polls GET /api/guides/{id} and shows job.progress meanwhile."""
    if model not in ("wonder", "spark"):
        raise HTTPException(400, "model must be wonder or spark")
    guide_id = store.new_id(title or (video.filename or "guide").rsplit(".", 1)[0])
    d = store.folder(guide_id)
    d.mkdir(parents=True)
    with (d / "video.mp4").open("wb") as out:
        shutil.copyfileobj(video.file, out)            # streams to disk, no full copy in memory
    store.write_job(guide_id, status="processing", progress="Queued", title=title or guide_id, user_title=title.strip(),
                    domain=domain, source_name=video.filename or "video.mp4")
    background.add_task(pipeline.run, guide_id, model, domain)
    return store.summary(guide_id)


@app.get("/api/guides/{guide_id}")
def get_guide(guide_id: str):
    job = store.read_job(guide_id) if _safe(guide_id) else {}
    guide = store.load_guide(guide_id) if _safe(guide_id) else None
    if guide is None and not job:
        raise HTTPException(404, "Guide not found")
    return {"job": job, "guide": guide}


@app.put("/api/guides/{guide_id}", response_model=Guide)
def update_guide(guide_id: str, guide: Guide):
    """The senior's edits from the review screen. Same validation as Wonder's answer."""
    _guide_or_404(guide_id)
    guide.id = guide_id
    try:
        guide = Guide.model_validate(guide.model_dump())
    except ValidationError as e:
        raise HTTPException(422, str(e))
    store.save_guide(guide)
    return guide


@app.post("/api/guides/{guide_id}/publish", response_model=Guide)
def publish(guide_id: str):
    guide = _guide_or_404(guide_id)
    guide.status = "published"
    store.save_guide(guide)
    store.write_job(guide_id, status="published", progress="")
    return guide


@app.get("/api/guides/{guide_id}/files/{name}")
def guide_file(guide_id: str, name: str):
    try:
        path = store.file_path(guide_id, name)
    except ValueError:
        raise HTTPException(400, "Bad path")
    if not path.is_file() or name.endswith(".json"):
        raise HTTPException(404, "No such file")
    return FileResponse(path)


def _safe(guide_id: str) -> bool:
    try:
        store.folder(guide_id)
        return True
    except ValueError:
        return False


# ── Live coach ─────────────────────────────────────────────────────────────
# Model calls block for seconds, so they run in a worker thread (run_in_threadpool);
# the server keeps answering other requests meanwhile.

@app.post("/api/coach/ask", response_model=coach.AskResult)
async def coach_ask(guide_id: str = Form(...), step_no: int = Form(...), question: str = Form(...),
                    frame: UploadFile | None = File(None)):
    guide = _guide_or_404(guide_id)
    step = _step_or_404(guide, step_no)
    if not question.strip():
        raise HTTPException(400, "Empty question")
    image = await _read_frame(frame)
    return await run_in_threadpool(coach.ask, guide, step, question.strip(), image)


@app.post("/api/coach/check", response_model=coach.CheckResult)
async def coach_check(guide_id: str = Form(...), step_no: int = Form(...), frame: UploadFile = File(...)):
    guide = _guide_or_404(guide_id)
    step = _step_or_404(guide, step_no)
    image = await _read_frame(frame)
    if image is None:
        raise HTTPException(400, "Empty frame")
    return await run_in_threadpool(coach.check, guide, step, image)


@app.websocket("/ws/asr")
async def ws_asr(ws: WebSocket):
    await asr_relay.handle(ws)


# ── The app ────────────────────────────────────────────────────────────────
# Mounted last, so /api and /ws routes win. html=True serves index.html for "/".
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="app")
