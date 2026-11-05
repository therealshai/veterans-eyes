# Veteran's Eyes: notes for coding agents (Muse Code, Claude Code)

A senior records one narrated repair video. The backend turns it into a guide (steps, parts,
tips, warnings, checks) with highlighted keyframes. A junior then does the job with a phone:
the app speaks each step, answers spoken questions, and checks the work at critical steps.
Hackathon: Meta Global AI Developer Hackathon 2026, deadline Nov 5 06:30 IST.

## Layout
- `backend/` FastAPI (Python 3.11+). Entry `backend/app.py`.
  - `models.py` the guide contract (Pydantic). `GuideDraft` = what Wonder returns (strict: every
    field required, no defaults); `Guide` = stored, adds keyframe fields.
  - `meta.py` the ONLY file that calls Meta's API (Wonder, Spark, SAM 3.1). Tests replace it.
  - `expert/` video → guide (`extract_guide.py`, Wonder) → keyframes (`keyframes.py`, SAM).
  - `live/coach.py` ask + check (Spark fast + SAM in parallel); `live/asr_relay.py` voice WebSocket.
  - `eval/industreal.py` checkpoint accuracy on IndustReal.
  - `fake.py` demo mode: canned model answers (on with `VE_FAKE=1` or when no key is set).
- `frontend/` Vite + React + TypeScript + Tailwind v4 + shadcn/ui (`src/components/ui`, hand-written
  shadcn files). Screens in `src/screens/`, API calls in `src/lib/api.ts`, hash routing.
- `docs/learn/` one explainer per module; `docs/DECISIONS.md` why things are the way they are.
- `data/guides/<id>/` runtime data (gitignored). `demo/` sample guides that ship with the repo.

## Commands
- Tests (no API calls): `python -m pytest`
- Backend: `uvicorn backend.app:app --reload` (http://localhost:8000/docs)
- Frontend dev: `cd frontend && npm run dev` (proxies /api and /ws to :8000); build: `npm run build`
- Demo mode: `VE_FAKE=1 uvicorn backend.app:app`
- Real capture: `bash scripts/run_capture.sh <video> <id> <domain>`

## Rules
- Never put API keys in code, README, or commits. Keys live in `.env` (see `.env.example`).
- Never commit Ego-Exo4D footage (`fixtures/egoexo_*`, guides with "egoexo" in the id): license.
- Every Meta call goes through `backend/meta.py`; every new behaviour gets a test with fakes.
- Live calls use `fast=True` (minimal reasoning, 1200-token cap): the ~4 s budget is measured, keep it.
- Keep strict-schema models free of defaults; add stored-only fields to `Step`/`Guide`, not the drafts.
- UI: plain shadcn, zinc neutrals; amber (`warn`) only for "look here"/warnings, green (`ok`) only
  for passed checks; touch targets ≥ 48 px; every AI state shown in words.
- When you change how a module works, update its note in `docs/learn/` and add a line to
  `docs/DECISIONS.md` if it is a decision.
