# Decisions

Newest first. One line of why per decision; details in docs/learn/.

## 2026-11-03
- **Live latency re-measured Nov 3, SPARK_FAST kept for now:** no empty replies, no median over 6 s; but a verdict hit the 400-token cap mid-JSON (out=400, truncated), so the cap is too tight for the verdict path — validate max 800 over 5 calls before changing it. Checkpoint regressed 3.98 → 5.25 s (over the 5 s rule).
- **Demo mode turns on by itself when no API key is set** (and says so on every screen): judges can run the public repo without credentials, as Meta asked. `VE_FAKE=0/1` forces it.
- **Sample guides ship in `demo/`** (our own footage only, 720p) and are copied into `data/guides/` on start.
- **IndustReal score uses the live checkpoint unchanged** (`coach.judge`); the reference is the same step done correctly in another recording; mistakes = rows in `PSR_labels_with_errors.csv` missing from `PSR_labels.csv`.
- **The senior's job name wins** over the title Wonder writes.
- **AGENTS.md** gives Muse Code (and Claude Code) the project rules.
- **Expert test clip = head camera only.** Ego-Exo4D's `ego_preview.mp4` is a 7-camera mosaic, which Wonder described as "multiple angles". `fixtures/egoexo_repair_ego.mp4` crops the left tile (398x448) and keeps the narration audio: closest to a chest-mounted phone.

## 2026-11-02
- **Scope: core loop + IndustReal score.** Cut: Hindi/Kannada voice, background watcher, auto step detection.
- **Claude writes the code, Syed runs, tests and learns it** (one learn note per module in docs/learn/).
- **Frontend: Vite + React + TypeScript + Tailwind + plain shadcn**, built to static files served by FastAPI: one server, one HTTPS tunnel.
- **Hash routes** (`#/guides/x/coach`): no server route config for the app's pages.
- **Push-to-talk, not always listening:** workshop noise; matches the ASR `PUSH_TO_TALK` mode.
- **The phone never calls Meta:** audio goes through `/ws/asr` so the API key stays on the server.
- **Keyframe = hand touching the part**, measured with `covered_by` (share of the part under the hand), not IoU: a hand is far bigger than a bolt.
- **Two-layer guide model:** `GuideDraft` (what Wonder must return, strict: all fields required) and `Guide` (adds keyframes, review flags, status).
- **Strict schemas are flattened** (no `$ref`) before sending: some providers reject `$ref` in strict mode.
- **Files, not a database:** `data/guides/<id>/` per guide; enough for a demo.
- **Fake mode (`VE_FAKE=1`)** answers every model call with canned replies: UI work and rehearsal without credits; doubles as the judges' no-key demo path.
- **Judges' rules (from Meta):** runs from the public repo's README; 3-minute video; no keys in the repo, `.env.example` instead; a credential-free demo path.

## 2026-10-27 (speed test, docs/speed_test.md)
- **Live Spark calls use minimal reasoning + 400-token cap:** median 8.2 s → 3.9 s, and the spread narrowed.
- **Checkpoints run Spark and SAM in parallel:** 4.0 s median, under the 5 s gate, so checks stay automatic on critical steps.
- **One realtime ASR stream per question, opened on button press:** the 1.5 s connect overlaps with the junior still speaking; final text arrives 0.4 s after release.
- **Wonder for expert capture only:** ~47 s per minute of video; never in the live loop.
