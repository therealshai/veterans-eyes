import asyncio
import base64
import inspect
import json
import os
import re
import ssl
import statistics
import sys
import time
import uuid
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
import certifi
import dotenv
import httpx
import websockets
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent    
FIXTURES = ROOT / "fixtures"
REPORT = ROOT / "docs" / "speed_test.md"
RESULTS_JSON = ROOT / "docs" / "speed_test.json"   # every call's latest numbers, merged across runs

dotenv.load_dotenv(ROOT / ".env")
API_KEY = os.getenv("META_API_KEY") 
BASE_URL = "https://api.meta.ai/v1"


SPARK_MODEL = "muse-spark-1.3"   # current documented Muse Spark model
WONDER_MODEL = "muse-wonder-1.0" #video
SAM_MODEL = "sam-3.1" #img segmentation
ASR_MODEL = "muse-voice-transcribe-1.0"  # audio transcription

FRAME_EXPERT = FIXTURES / "egoexo_frame_1.jpg"   
FRAME_JUNIOR = FIXTURES / "egoexo_frame_2.jpg"  
QUESTION_WAV = FIXTURES / "egoexo_narration_10s.wav"       
CLIP = FIXTURES / "egoexo_repair_clip.mp4"         # 30–60 s narrated repair

RUNS = 5            # cheap calls
WONDER_RUNS = 2     # expensive call: save credits

RATE = 24_000                               # samples per second
CHUNK_MS = 80                               # send audio in 80 ms pieces, like a mic would
CHUNK_BYTES = RATE * 2 * CHUNK_MS // 1000   # 16-bit audio = 2 bytes per sample

# Create clients ONCE and reuse them. Each new client opens a new TLS connection,
# which adds ~0.3–1 s to the first call; the real backend keeps connections warm too.
if not API_KEY:
    raise RuntimeError(
        "META_API_KEY is missing. Add it to the project-root .env file or environment."
    )

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
http = httpx.Client(
    base_url=BASE_URL,
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=120,
)
ssl_context = ssl.create_default_context(cafile=certifi.where())


# ── 2. Timing (done for you) ───────────────────────────────────────────────
# time.perf_counter() is Python's stopwatch: a float of seconds that only ever
# goes forward. The difference between two readings = elapsed time. It works
# the same inside async code, so streams use it too (see StreamTimer).

@dataclass
class Result:
    key: str
    label: str
    times: list[float] = field(default_factory=list)              # main number, one per good run
    extra: dict[str, list[float]] = field(default_factory=dict)   # sub-timings (upload, first_partial…)
    errors: list[str] = field(default_factory=list)
    sample: str = ""                                               # first output, cut short

    @property
    def median(self):
        return statistics.median(self.times) if self.times else None

    @property
    def slowest(self):
        return max(self.times) if self.times else None


class StreamTimer:
    """Stopwatch with named laps, for streams and multi-step calls.

    t = StreamTimer()          # starts now
    t.mark("first_partial")    # seconds since start; a repeated name keeps the FIRST time
    t.between("a", "b")        # seconds from mark a to mark b
    """

    def __init__(self):
        self.t0 = time.perf_counter()
        self.marks: dict[str, float] = {}

    def mark(self, name: str) -> None:
        self.marks.setdefault(name, time.perf_counter() - self.t0)

    def between(self, start: str, end: str) -> float:
        return self.marks[end] - self.marks[start]


def _run_once(fn):
    """Run fn once (sync or async). Returns (output, wall_seconds, timings).

    A call may return (output, {"name": seconds, ...}) to report sub-timings.
    If that dict has "total", it replaces the wall-clock time as the main number.
    """
    t0 = time.perf_counter()
    out = asyncio.run(fn()) if inspect.iscoroutinefunction(fn) else fn()
    wall = time.perf_counter() - t0
    timings = {}
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[1], dict):
        out, timings = out
    return out, wall, dict(timings)


def bench(key, label, fn, runs, warmup) -> Result:
    """Call fn `warmup` times (not counted), then `runs` times (counted)."""
    r = Result(key, label)
    for _ in range(warmup):
        try:
            _run_once(fn)
        except Exception:
            pass  # a failing call will show its error in the counted runs
    for i in range(1, runs + 1):
        try:
            out, wall, timings = _run_once(fn)
        except NotImplementedError as e:
            r.errors.append(f"not written yet: {e}")
            print(f"  skipped: not written yet ({e})")
            break
        except Exception as e:
            r.errors.append(f"run {i}: {type(e).__name__}: {e}")
            print(f"  run {i}: ERROR {type(e).__name__}: {e}")
            continue
        main_time = timings.pop("total", wall)
        r.times.append(main_time)
        for name, secs in timings.items():
            r.extra.setdefault(name, []).append(secs)
        if not r.sample:
            r.sample = " ".join(str(out).split())[:160]
        print(f"  run {i}: {main_time:.2f} s")
    return r


def _fmt(x):
    return "—" if x is None else f"{x:.2f}"


def checkpoint_verdict(results) -> str:
    """Apply the decision rule from the Oct 27 plan to the measured numbers."""
    by_key = {r.key: r for r in results}
    cp = by_key.get("checkpoint")
    if cp and cp.median is not None:
        total, source = cp.median, "measured in parallel"
    else:
        a, b = by_key.get("spark_verdict"), by_key.get("sam")
        if not (a and b and a.median is not None and b.median is not None):
            return "Not decided yet: needs successful runs of spark_verdict and sam."
        total, source = a.median + b.median, "Spark verdict + SAM, added up"
    if total < 5:
        rule = "under 5 s, so checkpoints run as designed"
    elif total <= 10:
        rule = "5–10 s, so send fewer frames and shorter prompts"
    else:
        rule = "over 10 s, so checks run only when the junior asks"
    return f"Checkpoint ({source}) = {total:.2f} s: {rule}."


def print_table(results) -> None:
    print(f"\n{'Call':<48}{'OK':>6}{'Median':>9}{'Slowest':>9}")
    for r in results:
        ok = f"{len(r.times)}/{len(r.times) + len(r.errors)}"
        print(f"{r.label:<48}{ok:>6}{_fmt(r.median):>9}{_fmt(r.slowest):>9}")
        for name, vals in r.extra.items():
            print(f"{'   ↳ ' + name:<48}{'':>6}{_fmt(statistics.median(vals)):>9}{_fmt(max(vals)):>9}")


def merge_with_saved(results) -> list:
    """Combine this run with earlier runs, so the report always shows every call.

    A call you just ran replaces its old numbers; calls you didn't run keep theirs.
    Stored in docs/speed_test.json; the .md report is rebuilt from it each time.
    """
    saved = {}
    if RESULTS_JSON.exists():
        for d in json.loads(RESULTS_JSON.read_text()):
            saved[d["key"]] = Result(**d)
    for r in results:
        saved[r.key] = r
    merged = [saved[k] for k in CALLS if k in saved]   # keep the CALLS order
    RESULTS_JSON.parent.mkdir(exist_ok=True)
    RESULTS_JSON.write_text(json.dumps([asdict(r) for r in merged], indent=2))
    return merged


def write_report(results) -> None:
    lines = [
        f"# Speed test — {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Seconds. {RUNS} counted runs per call ({WONDER_RUNS} for Wonder), after one uncounted warm-up for the cheap calls.",
        "",
        "| Call | OK | Median | Slowest | Sample output |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        ok = f"{len(r.times)}/{len(r.times) + len(r.errors)}"
        sample = r.sample.replace("|", "/")
        lines.append(f"| {r.label} | {ok} | {_fmt(r.median)} | {_fmt(r.slowest)} | {sample} |")
        for name, vals in r.extra.items():
            lines.append(f"| ↳ {name} | | {_fmt(statistics.median(vals))} | {_fmt(max(vals))} | |")
    lines += ["", f"**Decision:** {checkpoint_verdict(results)}", ""]
    errors = [(r.label, e) for r in results for e in r.errors]
    if errors:
        lines += ["## Errors", ""] + [f"- {label}: `{e[:300]}`" for label, e in errors] + [""]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines))
    print(f"Saved {REPORT.relative_to(ROOT)}")


# ── 3. Fixtures (TODO: you) ────────────────────────────────────────────────

def image_to_data_url(path: Path) -> str:
    """Return a JPEG data URL suitable for image input."""
    if not path.is_file():
        raise FileNotFoundError(f"Image fixture not found: {path}")
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"Image fixture is empty: {path}")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"

def read_pcm(path: Path) -> bytes:
    """Return raw signed 16-bit mono PCM samples from a supported WAV file."""
    if not path.is_file():
        raise FileNotFoundError(f"Audio fixture not found: {path}")

    try:
        with wave.open(str(path), "rb") as w:
            params = {
                "sample_rate": w.getframerate(),
                "channels": w.getnchannels(),
                "sample_width": w.getsampwidth(),
                "compression": w.getcomptype(),
            }
            if (
                params["sample_rate"] != RATE
                or params["channels"] != 1
                or params["sample_width"] != 2
                or params["compression"] != "NONE"
            ):
                raise ValueError(
                    f"{path.name} must be mono, 16-bit PCM WAV at {RATE} Hz; "
                    f"found {params}. Convert it with: "
                    f"ffmpeg -i input.wav -ac 1 -ar {RATE} "
                    "-c:a pcm_s16le -map_metadata -1 fixtures/question.wav"
                )
            pcm = w.readframes(w.getnframes())
    except wave.Error as exc:
        raise ValueError(f"{path} is not a readable PCM WAV file: {exc}") from exc

    if not pcm:
        raise ValueError(f"Audio fixture contains no samples: {path}")
    return pcm


def check_fixtures() -> None:
    missing = [p.name for p in (FRAME_EXPERT, FRAME_JUNIOR, QUESTION_WAV, CLIP) if not p.exists()]
    if missing:
        print(f"⚠ missing fixtures (calls that need them will error): {', '.join(missing)}")


QUESTION = "What part is the person's hand touching? Answer in one short sentence."

VERDICT_PROMPT = (
    "Image 1 is the expert's reference for this repair step. Image 2 is the "
    "junior's current view. Does image 2 match the expert's result for this step?"
)
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["match", "fix", "unclear"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}

SAM_PROMPT = "wheel"   # something surely in the frame; we're timing, not testing accuracy

WONDER_PROMPT = (
    "List the repair steps in order with start and end times, and every tip or "
    "warning the speaker says out loud."
)


# Settings for the "fast" variants: least thinking, short answers.
# max_output_tokens includes thinking tokens, so don't go much lower or the JSON gets cut off.
SPARK_FAST = {"reasoning": {"effort": "minimal"}, "max_output_tokens": 400}


def _log_usage(tag: str, response) -> None:
    """One line per call: output tokens and whether the reply was empty."""
    usage = getattr(response, "usage", None)
    out = getattr(usage, "output_tokens", None) if usage else None
    print(f"  [usage] {tag} out_tokens={out} empty={not (response.output_text or '').strip()}")


def spark_answer(fast: bool = False):
    """Call Muse Spark with one image and a short question; return its text."""
    image_url = image_to_data_url(FRAME_JUNIOR)
    response = client.responses.create(
        model=SPARK_MODEL,
        **(SPARK_FAST if fast else {}),   # fast=True adds reasoning + output cap
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": QUESTION},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    )
    _log_usage("answer", response)
    return response.output_text


def spark_verdict(fast: bool = False):
    """Compare the expert and junior frames and return a validated JSON verdict."""
    expert_url = image_to_data_url(FRAME_EXPERT)
    junior_url = image_to_data_url(FRAME_JUNIOR)
    response = client.responses.create(
        model=SPARK_MODEL,
        **(SPARK_FAST if fast else {}),   # fast=True adds reasoning + output cap
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": VERDICT_PROMPT},
                    {"type": "input_image", "image_url": expert_url},
                    {"type": "input_image", "image_url": junior_url},
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "verdict",
                "schema": VERDICT_SCHEMA,
                "strict": True,
            }
        },
    )
    _log_usage("verdict", response)
    data = json.loads(response.output_text)
    if data.get("verdict") not in {"match", "fix", "unclear"}:
        raise ValueError(f"Unexpected verdict value: {data.get('verdict')!r}")
    if not isinstance(data.get("reason"), str):
        raise ValueError("Verdict response is missing a string 'reason'.")
    if set(data) != {"verdict", "reason"}:
        raise ValueError(f"Unexpected verdict keys: {sorted(data)}")
    return data


def sam_segment():
    """Ask SAM 3.1 to segment the named object and return a compact summary.

    SAM 3.1 uses the Responses API. Its output_text contains special-token
    records with one box and mask per detected object; do not store those masks
    in the benchmark report.
    """
    image_url = image_to_data_url(FRAME_JUNIOR)
    response = client.responses.create(
        model=SAM_MODEL,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": SAM_PROMPT},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    )
    output = response.output_text or ""
    object_count = len(re.findall(r"<\|box;", output))
    if object_count:
        return f"{object_count} object(s) segmented"
    if not output.strip():
        return "0 objects segmented"
    # Preserve a short diagnostic if the API's output format changes.
    return f"Segmentation response received ({len(output)} output characters)"


# bench() calls functions with no arguments, hence these two tiny wrappers.
def spark_answer_fast():
    return spark_answer(fast=True)


def spark_verdict_fast():
    return spark_verdict(fast=True)


async def checkpoint_parallel():
    """Fast Spark verdict + SAM at the same time, the way the live coach will run them.

    asyncio.to_thread runs each normal function in a background thread; gather
    waits for both. Both mostly wait on the network, so the waits overlap and the
    total is close to the slower call, not the sum.
    """
    verdict, highlight = await asyncio.gather(
        asyncio.to_thread(spark_verdict_fast),
        asyncio.to_thread(sam_segment),
    )
    return {"verdict": verdict, "sam": highlight}


def transcribe_file():
    """Transcribe the complete WAV with the multipart file-transcription API."""
    if not QUESTION_WAV.is_file():
        raise FileNotFoundError(f"Audio fixture not found: {QUESTION_WAV}")

    request_settings = {
        "mode": "PUSH_TO_TALK",
        "model": ASR_MODEL,
        "audioEncoding": "WAV",
    }
    with QUESTION_WAV.open("rb") as audio:
        response = http.post(
            "/asr/transcribe",
            params={"sessionId": f"speedtest-{uuid.uuid4()}"},
            files={
                "request": (None, json.dumps(request_settings), "application/json"),
                "audio": (QUESTION_WAV.name, audio, "audio/wav"),
            },
        )
    response.raise_for_status()
    payload = response.json()
    transcript = payload.get("transcript")
    if not isinstance(transcript, str):
        raise RuntimeError(f"ASR response did not contain transcript text: {payload}")
    return transcript


async def transcribe_realtime():
    """Stream the WAV at real-time pace and measure the wait after audio ends."""
    pcm = read_pcm(QUESTION_WAV)
    uri = f"wss://api.meta.ai/v1/asr/realtime?sessionId=speedtest-{uuid.uuid4()}"
    t = StreamTimer()
    final_text = None

    async with websockets.connect(uri, open_timeout=30, ssl=ssl_context) as ws:
        await ws.send(
            json.dumps(
                {
                    "authorization": {"accessToken": f"Bearer {API_KEY}"},
                    "audioEncoding": "PCM_24KHZ",
                    "model": ASR_MODEL,
                    "mode": "PUSH_TO_TALK",
                    "partialMode": "CUMULATIVE",
                    "emitAudioProgress": False,
                }
            )
        )
        handshake = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if "sessionId" not in handshake:
            raise RuntimeError(f"ASR handshake failed: {handshake}")
        t.mark("connected")

        async def receive():
            nonlocal final_text
            async for message in ws:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                if event.get("type") == "error":
                    raise RuntimeError(
                        f"ASR error (session {event.get('sessionId', handshake['sessionId'])}): "
                        f"{event.get('message', event)}"
                    )
                if event.get("type") != "transcript":
                    continue
                t.mark("first_partial")
                if event.get("final"):
                    t.mark("final")
                    final_text = event.get("transcript", "")
                    return

        receiver = asyncio.create_task(receive())
        try:
            t.mark("speech_start")
            for i in range(0, len(pcm), CHUNK_BYTES):
                await ws.send(pcm[i:i + CHUNK_BYTES])
                await asyncio.sleep(CHUNK_MS / 1000)
            t.mark("speech_end")
            await ws.send(json.dumps({"type": "endStream"}))
            await asyncio.wait_for(receiver, timeout=30)
        finally:
            if not receiver.done():
                receiver.cancel()
                try:
                    await receiver
                except asyncio.CancelledError:
                    pass

    if "final" not in t.marks:
        raise RuntimeError("ASR socket ended without a final transcript.")
    return final_text, {
        "total": t.between("speech_end", "final"),
        "connect": t.marks["connected"],
        "first_partial": t.between("speech_start", "first_partial"),
    }


def wonder_video():
    """Upload the narrated repair clip and ask Muse Wonder to summarize it."""
    if not CLIP.is_file():
        raise FileNotFoundError(f"Video fixture not found: {CLIP}")

    t = StreamTimer()
    with CLIP.open("rb") as video:
        uploaded_file = client.files.create(file=video, purpose="user_data")
    t.mark("uploaded")

    response = client.responses.create(
        model=WONDER_MODEL,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": WONDER_PROMPT},
                    {"type": "input_file", "file_id": uploaded_file.id},
                ],
            }
        ],
    )
    t.mark("answered")
    return response.output_text, {
        "upload": t.marks["uploaded"],
        "analysis": t.between("uploaded", "answered"),
    }


# ── 5. Main (done for you) ─────────────────────────────────────────────────

CALLS = {
    # key            label                                              function             runs         warm-up
    "spark":         ("1. Spark: plain answer",                         spark_answer,        RUNS,        1),
    "spark_verdict": ("2. Spark: JSON verdict",                         spark_verdict,       RUNS,        1),
    "sam":           ("3. SAM 3.1: segment one prompt",                 sam_segment,         RUNS,        1),
    "spark_fast":         ("1f. Spark: plain answer, minimal reasoning",  spark_answer_fast,   RUNS,        1),
    "spark_verdict_fast": ("2f. Spark: JSON verdict, minimal reasoning",  spark_verdict_fast,  RUNS,        1),
    "checkpoint":         ("2f+3. Checkpoint: Spark + SAM in parallel",   checkpoint_parallel, RUNS,        1),
    "asr_file":      ("4a. Transcribe: file",                           transcribe_file,     RUNS,        1),
    "asr_live":      ("4b. Transcribe: realtime (wait after speech)",   transcribe_realtime, RUNS,        0),
    "wonder":        ("5. Wonder: video + audio",                       wonder_video,        WONDER_RUNS, 0),
}


def main() -> None:
    wanted = sys.argv[1:] or list(CALLS)
    unknown = [k for k in wanted if k not in CALLS]
    if unknown:
        sys.exit(f"Unknown call(s): {unknown}. Choose from: {list(CALLS)}")
    check_fixtures()
    results = []
    for key in wanted:
        label, fn, runs, warmup = CALLS[key]
        print(f"\n▶ {label}")
        results.append(bench(key, label, fn, runs, warmup))
    print_table(results)                  # just this run
    all_results = merge_with_saved(results)
    print("\n" + checkpoint_verdict(all_results))
    write_report(all_results)             # every call, latest numbers


if __name__ == "__main__":
    main()
