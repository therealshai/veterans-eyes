"""Shared settings: paths, model ids, the API client. Every module imports from here.

The client is created on first use (get_client), so tests and offline tools
run without an API key.
"""
import os
from functools import lru_cache
from pathlib import Path

import dotenv

ROOT = Path(__file__).resolve().parent.parent       # the repo folder
dotenv.load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
GUIDES_DIR = DATA_DIR / "guides"                     # one folder per guide (gitignored)
PROMPTS_DIR = ROOT / "backend" / "prompts"
FRONTEND_DIST = ROOT / "frontend" / "dist"           # built app, served by FastAPI
DEMO_DIR = ROOT / "demo"                             # sample guides committed to the repo (our own footage only)

API_KEY = os.getenv("META_API_KEY", "")
BASE_URL = "https://api.meta.ai/v1"
ASR_URL = "wss://api.meta.ai/v1/asr/realtime"

SPARK_MODEL = "muse-spark-1.3"
WONDER_MODEL = "muse-wonder-1.0"
SAM_MODEL = "sam-3.1"
ASR_MODEL = "muse-voice-transcribe-1.0"

# Live calls: least thinking, short answers (Oct 27: Spark 8.2 s -> 3.9 s median).
# Cap is 1200, not 400: the cap covers hidden reasoning too, and long questions
# exhausted 400 mid-sentence live (Nov 3). Visible answers stay 1-2 sentences.
SPARK_FAST = {"reasoning": {"effort": "minimal"}, "max_output_tokens": 1200}


@lru_cache(maxsize=1)
def get_client():
    """One shared OpenAI-compatible client for Meta's API (reuses its connections)."""
    if not API_KEY:
        raise RuntimeError("META_API_KEY is missing: add it to .env in the repo folder.")
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)
