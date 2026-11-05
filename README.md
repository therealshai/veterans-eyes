# Veteran's Eyes

A senior records one narrated repair. Veteran's Eyes turns it into a step-by-step guide with the
exact parts highlighted, then coaches a junior through the same job by voice on a phone: it speaks
each step, answers spoken questions, and checks the work at critical steps before damage is done.

Built for the Meta Global AI Developer Hackathon 2026 (indie track) with Meta's models:

| Model | Job |
|---|---|
| Muse Wonder | watches the expert video with its narration → structured guide (steps, parts, tips, warnings, checks) |
| SAM 3.1 | finds the hand and the part in each step → highlighted keyframes; finds the part again on the junior's camera |
| Muse Spark 1.3 | live answers and checkpoint verdicts (minimal reasoning, ~4 s) |
| Muse Voice Transcribe | realtime speech from the phone, relayed through the backend |

## Run it

Needs Python 3.11+, Node 20.19+ (or 22.12+) and ffmpeg. Or just Docker (below).

```bash
git clone <this repo> && cd veterans-eyes
cp .env.example .env              # then paste your Meta Model API key after META_API_KEY=
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000. A sample guide is ready to coach.

**No API key? Demo mode.** With `META_API_KEY` empty, the app starts in demo mode and says so on
every screen: steps, answers and checks are canned examples, nothing is called or billed. Every
screen and flow can be tried this way. Add a key for real answers. Force either way with
`VE_FAKE=1` or `VE_FAKE=0` in `.env`.

**Docker:**
```bash
docker build -t veterans-eyes .
docker run -p 8000:8000 --env-file .env veterans-eyes     # with your key
docker run -p 8000:8000 veterans-eyes                     # demo mode
```

**On a phone** (camera and mic need HTTPS): `cloudflared tunnel --url http://localhost:8000`,
then open the https link it prints. Choose "Replay" on the coach screen to use a recorded video
instead of the camera.

**Command line:**
- Tests, no API calls: `python -m pytest`
- Guide from a video: `bash scripts/run_capture.sh path/to/video.mp4 my-guide two-wheeler`
- IndustReal accuracy: `python -m backend.eval.industreal <IndustReal folder>` (see `docs/learn/09`)

## How it works
See `docs/learn/` (01 to 09): one short note per module, and `docs/DECISIONS.md` for why.

Data credits: IndustReal (Schoonbeek et al., WACV 2024, Apache-2.0) for the accuracy test.
Senior's video: SPORTSBIKESHOP.co.uk, How to clean and lube your motorcycle chain - Sportsbikeshop, https://www.youtube.com/watch?v=mtxkoA-mz_U, licensed CC BY.
Ego-Exo4D was used for development testing only and is not included in this repo.
