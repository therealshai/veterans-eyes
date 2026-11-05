"""Voice relay failure paths: Meta errors reach the phone as words, stray
messages are ignored, and a dropped socket leaves no task behind."""
import json
import threading

from fastapi.testclient import TestClient

from backend.app import app
from backend.live import asr_relay

client = TestClient(app)


async def _counter(audio, to_phone):
    got = b""
    while (chunk := await audio.get()) is not None:
        got += chunk
    await to_phone({"type": "final", "text": f"{len(got)} bytes"})


def test_meta_error_reaches_phone_as_error(monkeypatch):
    async def boom(audio, to_phone):
        raise RuntimeError("ASR exploded")

    monkeypatch.setattr(asr_relay, "_meta_stream", boom)
    with client.websocket_connect("/ws/asr") as ws:
        ws.send_text(json.dumps({"type": "start"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error" and "ASR exploded" in msg["text"]
        ws.send_text(json.dumps({"type": "stop"}))  # tidy close after the failure


def test_stop_without_start_is_ignored(monkeypatch):
    monkeypatch.setattr(asr_relay, "_meta_stream", _counter)
    with client.websocket_connect("/ws/asr") as ws:
        ws.send_text(json.dumps({"type": "stop"}))  # stray: no stream open, must not break anything
        ws.send_text(json.dumps({"type": "start"}))
        ws.send_bytes(b"\x00" * 100)
        ws.send_text(json.dumps({"type": "stop"}))
        assert json.loads(ws.receive_text()) == {"type": "final", "text": "100 bytes"}


def test_closing_mid_utterance_leaves_no_task(monkeypatch):
    done = threading.Event()

    async def slow(audio, to_phone):
        try:
            while (chunk := await audio.get()) is not None:
                pass
        finally:
            done.set()

    monkeypatch.setattr(asr_relay, "_meta_stream", slow)
    with client.websocket_connect("/ws/asr") as ws:
        ws.send_text(json.dumps({"type": "start"}))
        ws.send_bytes(b"\x00" * 100)
        # no "stop": the socket just goes away
    assert done.wait(5), "the utterance task was still running after disconnect"
