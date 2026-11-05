# Submission kit

Fill the [brackets] with tonight's numbers. Everything else is ready to paste.

## Project name
Veteran's Eyes

## One-liner
A senior records one narrated repair; Veteran's Eyes turns it into a guide with the exact parts highlighted, then coaches a junior through the same job by voice and catches mistakes before damage is done.

## Description (paste into the form)
Skilled trades are losing their experts faster than they can train new ones. The knowledge that matters, like "cover the brake disc before you spray" or "lube the rollers, not the plates", lives in a senior's head and rarely gets written down.

Veteran's Eyes captures it from one video. A senior films a repair from the chest and talks through it. Muse Wonder watches the video and listens to the narration, then returns a structured guide: steps with times, the parts and tools involved, the expert's tips and warnings, and which steps need a check. SAM 3.1 finds the hand and the part in each step and picks the moment they touch, so every step gets a highlighted keyframe. The senior reviews the guide in a web app and publishes it.

A junior then does the job with a phone in a chest mount. The app speaks each step. The junior can hold a button and ask out loud ("which side do I spray?"); Muse Voice Transcribe turns speech into text through our backend, and Muse Spark answers from the current camera frame and the expert's own tips. On critical steps the junior taps "Check my work": Spark compares their frame with the expert's keyframe while SAM finds the part on their camera, and the coach says "matches", "fix this" with what to change, or "can't see clearly".

We measured everything we rely on live: a checkpoint (Spark and SAM in parallel) takes [4.0] s median, a spoken answer is final [0.4] s after the junior stops talking, and Spark with minimal reasoning answers in [3.9] s. To test whether checks catch real mistakes, we ran the same checkpoint on IndustReal, an industrial assembly dataset with labeled errors: it caught [X of Y] mistakes with [Z]% false alarms on correct steps.

## How we used Meta's models
| Model | Job |
|---|---|
| Muse Wonder | Watches the expert's video with its narration and returns the whole guide as strict JSON, validated by Pydantic, with one automatic retry that sends the validation error back |
| SAM 3.1 | Finds "hand" and each part across sampled frames; the keyframe is where the hand covers the part. Live, it finds the part again on the junior's camera |
| Muse Spark 1.3 | Live answers and checkpoint verdicts, minimal reasoning, strict JSON verdicts; also suggests simpler part names when SAM finds nothing |
| Muse Voice Transcribe | Realtime push-to-talk speech, relayed through the backend so the API key never reaches the phone |
| Muse Code | Used to test and harden the project: it ran our test plan, found a microphone resampling bug at 44.1 kHz and a strict-schema bug, and added end-to-end tests |

## Technical highlights
- Strict structured output end to end; every model call goes through one module, so all [77+] tests run with fakes and no credits
- Keyframe selection by hand-part contact (`covered_by`) instead of IoU, which stays near zero for a hand on a small bolt
- Push-to-talk audio: an AudioWorklet resamples the mic to 24 kHz 16-bit PCM in 80 ms chunks; the server opens the speech stream on button press so the 1.5 s connect overlaps with speaking
- Demo mode: without an API key the app runs on canned answers and says so on every screen, so anyone can try every flow from the public repo
- One command to run: `uvicorn backend.app:app` (or the Dockerfile); replay mode lets any recorded video stand in for the camera

## Try it
Repo: [GitHub URL]. Video: [YouTube/Drive URL].
`cp .env.example .env`, add a Meta Model API key (or leave it empty for demo mode), `pip install -r requirements.txt`, `cd frontend && npm install && npm run build && cd ..`, `uvicorn backend.app:app`, open http://localhost:8000.

Data: IndustReal (Schoonbeek et al., WACV 2024, Apache-2.0). Ego-Exo4D was used only for internal development testing and is not included or shown.

---

# 3-minute video script

About 150 words a minute: read it at a calm pace. [B-roll] = what's on screen.

**0:00–0:20 · The problem**
[Close-up: chain, brake disc, your hands]
"Every workshop has one person who just knows. Cover the brake disc before you spray. Lube the rollers, not the plates. When that person retires, the knowledge leaves with them. And a junior who gets the brake disc wrong can't stop the bike."

**0:20–0:55 · The senior records once**
[Senior take, sped up; then the upload screen; then the guide appearing in Review]
"Veteran's Eyes starts with one video. The senior films the job from the chest and talks through it. Muse Wonder watches and listens, and returns a step-by-step guide: the instruction, the parts, the tools, and the senior's own tips and warnings. Then SAM 3.1 finds the hand and the part in every step and picks the moment they touch, so each step gets a highlighted keyframe. The senior fixes anything wrong, and publishes."

**0:55–1:55 · The junior is coached live**
[Split screen: over-the-shoulder camera + phone screen recording]
"Now a junior does the same job, with the phone on their chest. Each step is spoken." [let the app speak one step]
"They can just ask." [junior: "Which side do I spray?" app answers]
"That answer is the senior's own tip, from the video."
[the deliberate mistake: spray on the outer plates, tap Check my work]
"On critical steps, the coach checks the work. Muse Spark compares the junior's camera with the expert's keyframe, while SAM finds the part again." [verdict appears: Fix this, amber box]
"Caught, before it matters." [fix, check again: Matches the expert]

**1:55–2:25 · Does it catch real mistakes?**
[IndustReal footage, then docs/industreal_results.md numbers on screen]
"To test the checks, we ran them on IndustReal, an industrial assembly dataset with labeled mistakes. Same checkpoint, no changes: it caught [X of Y] real mistakes, with [Z] percent false alarms. Same system, a different trade."

**2:25–2:45 · How it's built**
[Architecture slide: phone → FastAPI → Wonder, SAM 3.1, Spark, Voice Transcribe]
"Four Meta models, each doing one job: Wonder for understanding the expert, SAM for seeing parts, Spark for fast answers and checks in about four seconds, Voice Transcribe for hands-free questions. We used Muse Code to test and harden it."

**2:45–3:00 · Close**
[Summary screen: steps, checks passed, mistakes caught, time]
"One recording from a senior. Every junior after that gets their eyes. Veteran's Eyes."
